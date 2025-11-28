from typing import Any, Awaitable, Callable, Self
from abc import ABC, abstractmethod
import asyncio
from collections.abc import Hashable
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import time

try:
    from concurrent.futures import InterpreterPoolExecutor
except ImportError:

    class InterpreterPoolExecutor(Executor):
        def __init__(self, *args, **kwargs): ...


from dataclasses import dataclass
from functools import cached_property, partial
from multiprocessing.context import BaseContext
import sys
from uuid import UUID

from anyio import CancelScope, Semaphore, create_task_group, to_interpreter, to_process, to_thread
from anyio.abc import TaskGroup as AnyIOTaskGroup

from filen._logging import logger

type TaskId = str | int | UUID | Hashable | tuple[Hashable, ...]


class TaskGroup:
    """Task group to run sync code in tasks with storing results by id"""

    def __init__(self, executor: Executor, exception_in_result: bool = False):
        self._executor = executor
        self._exception_in_result = exception_in_result
        self._tasks = {}
        self._results = {}
        self._ts = 0

    @property
    def results(self) -> dict[TaskId, Any]:
        return self._results

    def add_task[T, **P](
        self,
        task_id: TaskId,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ):
        if task_id in self._results:
            raise ValueError(f'A task with task_id {task_id} is already added.')

        # keep the order of results in the order tasks were added
        self._results[task_id] = None

        task = self._executor.submit(func, *args, **kwargs)
        self._tasks[task] = task_id

    def __enter__(self) -> Self:
        self._ts = time.monotonic()
        self._results.clear()
        self._tasks.clear()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        task_count = len(self._results)
        excs = []

        for task in as_completed(self._tasks):
            task_id = self._tasks[task]

            if exc := task.exception():
                if self._exception_in_result:
                    self._results[task_id] = exc
                else:
                    excs.append(exc)
            else:
                self._results[task_id] = task.result()

        if excs:
            self._results.clear()
            raise ExceptionGroup('unhandled errors in a TaskGroup', excs)
        else:
            took = time.monotonic() - self._ts
            logger.debug('All tasks (%d) in the task group have been completed (took: %.4fs)', task_count, took)


class AsyncTaskGroup:
    """Task group to run sync/async code in async tasks with storing results by id"""

    def __init__(
        self,
        runner: 'AsyncRunnerBase',
        concurrency: int | None = None,
        exception_in_result: bool = False,
    ) -> None:
        self._runner = runner
        self._runner_name = type(runner).__name__
        self._exception_in_result = exception_in_result
        self._tg: AnyIOTaskGroup | None = None
        self._concurrency = Semaphore(concurrency or sys.maxsize)
        self._results = {}
        self._ts = 0

    @property
    def results(self) -> dict[TaskId, Any]:
        return self._results

    @property
    def cancel_scope(self) -> CancelScope:
        if not self._tg:
            raise ValueError('Task group is not initialized. The context manager must be used.')
        return self._tg.cancel_scope

    def add_task[T, **P](
        self,
        task_id: TaskId,
        func: Callable[P, T | Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """Run a task function in the group concurrently"""

        if self._tg is None:
            raise ValueError('Task group is not initialized. The context manager must be used.')

        if task_id in self._results:
            raise ValueError(f'A task with task_id {task_id} is already added.')

        # keep the order of results in the order tasks were added
        self._results[task_id] = None

        async def afunc(*a):
            async with self._concurrency:
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*a, **kwargs)
                    else:
                        result = await self._runner.run_sync(func, *a, **kwargs)
                except Exception as exc:
                    if not self._exception_in_result:
                        raise
                    self._results[task_id] = exc
                else:
                    self._results[task_id] = result

        name = f'{self._runner_name}-Task-{task_id}'
        self._tg.start_soon(afunc, *args, name=name)

    async def __aenter__(self) -> Self:
        self._ts = time.monotonic()
        self._results.clear()
        self._tg = create_task_group()
        await self._tg.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        task_count = len(self._results)
        try:
            await self._tg.__aexit__(exc_type, exc_val, exc_tb)
            if self._tg.cancel_scope.cancelled_caught:
                self._results.clear()
            self._tg = None
        except Exception:
            if not self._exception_in_result:
                self._results.clear()
            raise
        else:
            took = time.monotonic() - self._ts
            logger.debug('All tasks (%d) in the task group have been completed (took: %.4fs)', task_count, took)


class AbstractRunner[TTaskGroup: TaskGroup | AsyncTaskGroup](ABC):
    """Abstract class for all runners"""

    @abstractmethod
    def task_group(self, exception_in_result: bool = False) -> TTaskGroup:
        pass


class RunnerBase(AbstractRunner[TaskGroup]):
    """Base runner to run sync code with support of parallel execution"""

    @property
    @abstractmethod
    def _executor(self) -> Executor:
        pass

    def task_group(self, exception_in_result: bool = False) -> TaskGroup:
        return TaskGroup(self._executor, exception_in_result=exception_in_result)

    def shutdown(self, wait: bool = True, cancel_tasks: bool = False) -> None:
        self._executor.shutdown(wait, cancel_futures=cancel_tasks)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        return self._executor.__exit__(exc_type, exc_val, exc_tb)


@dataclass
class ThreadRunner[**P](RunnerBase):
    """Thread pool runner"""

    max_workers: int | None = None
    initializer: Callable[P, None] | None = None
    initargs: P.args = ()

    @cached_property
    def _executor(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix=type(self).__name__,
            initializer=self.initializer,
            initargs=self.initargs,
        )


@dataclass
class ProcessRunner[**P](RunnerBase):
    """Process pool runner"""

    max_workers: int | None = None
    mp_context: BaseContext | None = None
    initializer: Callable[P, None] | None = None
    initargs: P.args = ()
    max_tasks_per_child: int | None = None

    @cached_property
    def _executor(self) -> ProcessPoolExecutor:
        return ProcessPoolExecutor(
            max_workers=self.max_workers,
            mp_context=self.mp_context,
            initializer=self.initializer,
            initargs=self.initargs,
            max_tasks_per_child=self.max_tasks_per_child,
        )


@dataclass
class InterpreterRunner[**P](RunnerBase):
    """Interpreter pool runner"""

    max_workers: int | None = None
    initializer: Callable[P, None] | None = None
    initargs: P.args = ()

    def __post_init__(self):
        if sys.version_info < (3, 14):
            raise RuntimeError('InterpreterRunner can be used only in Python 3.14 and above.')

    @cached_property
    def _executor(self) -> InterpreterPoolExecutor:
        return InterpreterPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix=type(self).__name__,
            initializer=self.initializer,
            initargs=self.initargs,
        )


@dataclass
class AsyncRunnerBase(AbstractRunner[AsyncTaskGroup]):
    """Base runner to run sync code in asynchronous event loop"""

    concurrency: int | None = None

    @property
    @abstractmethod
    def _run_sync[T](self) -> Callable[[Callable[..., T], ...], Awaitable[T]]:
        pass

    async def run_sync[T, **P](self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Run a sync function in asynchronous context"""

        return await self._run_sync(partial(func, **kwargs), *args)

    def task_group(self, concurrency: int | None = None, exception_in_result: bool = False) -> AsyncTaskGroup:
        """Create task group to run several tasks concurrently"""

        concurrency = concurrency or self.concurrency
        logger.debug('Task group concurrency: %s', concurrency)

        return AsyncTaskGroup(self, concurrency=concurrency, exception_in_result=exception_in_result)


@dataclass
class AsyncThreadRunner(AsyncRunnerBase):
    """Run sync code in a thread pool"""

    abandon_on_cancel: bool = False
    cancellable: bool | None = None
    limiter: to_thread.CapacityLimiter | None = None

    @cached_property
    def _run_sync(self):
        return partial(
            to_thread.run_sync,
            abandon_on_cancel=self.abandon_on_cancel,
            cancellable=self.cancellable,
            limiter=self.limiter,
        )


@dataclass
class AsyncProcessRunner(AsyncRunnerBase):
    """Run sync code in a process pool"""

    cancellable: bool | None = None
    limiter: to_process.CapacityLimiter | None = None

    @cached_property
    def _run_sync(self):
        return partial(to_process.run_sync, cancellable=self.cancellable, limiter=self.limiter)


@dataclass
class AsyncInterpreterRunner(AsyncRunnerBase):
    """Run sync code in a separate interpreter"""

    limiter: to_interpreter.CapacityLimiter | None = None

    def __post_init__(self):
        if sys.version_info < (3, 14):
            raise RuntimeError('AsyncInterpreterRunner can be used only in Python 3.14 and above.')

    @cached_property
    def _run_sync(self):
        return partial(to_interpreter.run_sync, limiter=self.limiter)

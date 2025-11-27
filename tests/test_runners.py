import sys
import time
from uuid import uuid4

from anyio import sleep
import pytest

from filen.runners import (
    AsyncInterpreterRunner,
    AsyncProcessRunner,
    AsyncThreadRunner,
    InterpreterRunner,
    ProcessRunner,
    ThreadRunner,
)


def task(n, tid):
    return n, tid


async def atask(n, tid):
    return n, tid


def long_task(n):
    time.sleep(5.0)
    return n


async def long_atask(n):
    await sleep(5.0)
    return n


def error(n):
    raise ValueError(n)


@pytest.fixture(params=[ThreadRunner, ProcessRunner, InterpreterRunner])
def runner(request):
    runner_cls = request.param

    if issubclass(runner_cls, InterpreterRunner) and sys.version_info < (3, 14):
        pytest.skip('InterpreterRunner works only in Python >= 3.14')

    return runner_cls()


@pytest.fixture(params=[AsyncThreadRunner, AsyncProcessRunner, AsyncInterpreterRunner])
def async_runner(request):
    runner_cls = request.param

    if issubclass(runner_cls, AsyncInterpreterRunner) and sys.version_info < (3, 14):
        pytest.skip('AsyncInterpreterRunner works only in Python >= 3.14')

    return runner_cls()


def test_runner_task_group(runner):
    task_ids = [1, 2, 't1', 't2', uuid4(), uuid4()]

    with runner:
        r = []

        with runner.task_group() as tg:
            for n, tid in enumerate(task_ids):
                r.append((tid, (n, tid)))
                tg.add_task(tid, task, n, tid=tid)

        assert list(tg.results.items()) == r


def test_runner_task_group_error(runner):
    with runner:
        with runner.task_group(exception_in_result=True) as tg:
            tg.add_task('t1', task, 0, 't1')

            for n in range(1, 5):
                tg.add_task(n, error, n)

        for tid, r in tg.results.items():
            if isinstance(tid, int):
                assert isinstance(r, ValueError)
                assert r.args[0] == tid
            else:
                assert r == (0, tid)

        with pytest.raises(ExceptionGroup):
            with runner.task_group() as tg:
                tg.add_task(1, task, 0, 1)
                tg.add_task(2, error, 1)
                tg.add_task(3, error, 2)

        assert len(tg.results) == 0


async def test_async_runner_run_sync(async_runner):
    res = await async_runner.run_sync(task, 1, 1)
    assert res == (1, 1)

    res = await async_runner.run_sync(task, 2, 2)
    assert res == (2, 2)


async def test_async_runner_task_group(async_runner):
    task_ids1 = [1, 2, 't1', 't2', uuid4(), uuid4()]
    task_ids2 = [3, 4, 't3', 't4', uuid4(), uuid4()]
    r = []

    async with async_runner.task_group() as tg:
        for n, tid in enumerate(task_ids1):
            r.append((tid, (n, tid)))
            tg.add_task(tid, task, n, tid=tid)

        for n, tid in enumerate(task_ids2):
            r.append((tid, (n, tid)))
            tg.add_task(tid, atask, n, tid=tid)

    assert list(tg.results.items()) == r


async def test_async_runner_task_group_error(async_runner):
    with pytest.raises(ExceptionGroup):
        async with async_runner.task_group() as tg:
            tg.add_task(1, task, 1, tid=1)
            tg.add_task(2, atask, 2, tid=2)
            tg.add_task(3, error, 3)

    assert len(tg.results) == 0

    async with async_runner.task_group(exception_in_result=True) as tg:
        tg.add_task(1, task, 1, tid=1)
        tg.add_task(2, error, 2)
        tg.add_task(3, atask, 3, tid=3)

    assert tg.results[1] == (1, 1)
    assert tg.results[3] == (3, 3)

    assert isinstance(tg.results[2], ValueError)
    assert tg.results[2].args[0] == 2


@pytest.mark.parametrize('runner_cls', [AsyncThreadRunner, AsyncProcessRunner])
async def test_async_runner_task_group_cancel(runner_cls):
    runner = runner_cls(cancellable=True)

    async with runner.task_group() as tg:
        tg.add_task(1, long_task, 1)
        tg.add_task(2, long_atask, 2)

        await sleep(0.5)
        tg.cancel_scope.cancel('timeout')

    assert len(tg.results) == 0

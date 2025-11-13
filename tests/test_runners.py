import sys
from uuid import uuid4

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


def error(n):
    raise ValueError(n)


def maybe_skip_interpreter_tests(runner_cls):
    if issubclass(runner_cls, InterpreterRunner) and sys.version_info < (3, 14):
        pytest.skip('InterpreterRunner works only in Python >= 3.14')

    elif issubclass(runner_cls, AsyncInterpreterRunner) and sys.version_info < (3, 13):
        pytest.skip('AsyncInterpreterRunner works only in Python >= 3.13')


@pytest.mark.parametrize('runner_cls', [ThreadRunner, ProcessRunner, InterpreterRunner])
def test_runner_task_group(runner_cls):
    maybe_skip_interpreter_tests(runner_cls)

    task_ids = [1, 2, 't1', 't2', uuid4(), uuid4()]

    with runner_cls() as runner:
        r = []

        with runner.task_group() as tg:
            for n, tid in enumerate(task_ids):
                r.append((tid, (n, tid)))
                tg.add_task(tid, task, n, tid=tid)

        assert list(tg.results.items()) == r


@pytest.mark.parametrize('runner_cls', [ThreadRunner, ProcessRunner, InterpreterRunner])
def test_runner_task_group_error(runner_cls):
    maybe_skip_interpreter_tests(runner_cls)

    with runner_cls() as runner:
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


@pytest.mark.parametrize('runner_cls', [AsyncThreadRunner, AsyncProcessRunner, AsyncInterpreterRunner])
async def test_async_runner_run_sync(runner_cls):
    maybe_skip_interpreter_tests(runner_cls)

    runner = runner_cls()

    res = await runner.run_sync(task, 1, 1)
    assert res == (1, 1)

    res = await runner.run_sync(task, 2, 2)
    assert res == (2, 2)


@pytest.mark.parametrize('runner_cls', [AsyncThreadRunner, AsyncProcessRunner, AsyncInterpreterRunner])
async def test_async_runner_task_group(runner_cls):
    maybe_skip_interpreter_tests(runner_cls)

    task_ids1 = [1, 2, 't1', 't2', uuid4(), uuid4()]
    task_ids2 = [3, 4, 't3', 't4', uuid4(), uuid4()]
    r = []

    runner = runner_cls()

    async with runner.task_group() as tg:
        for n, tid in enumerate(task_ids1):
            r.append((tid, (n, tid)))
            tg.add_task(tid, task, n, tid=tid)

        for n, tid in enumerate(task_ids2):
            r.append((tid, (n, tid)))
            tg.add_task(tid, atask, n, tid=tid)

    assert list(tg.results.items()) == r


@pytest.mark.parametrize('runner_cls', [AsyncThreadRunner, AsyncProcessRunner, AsyncInterpreterRunner])
async def test_async_runner_task_group_error(runner_cls):
    maybe_skip_interpreter_tests(runner_cls)

    runner = runner_cls()

    with pytest.raises(ExceptionGroup):
        async with runner.task_group() as tg:
            tg.add_task(1, task, 1, tid=1)
            tg.add_task(2, atask, 2, tid=2)
            tg.add_task(3, error, 3)

    assert len(tg.results) == 0

    async with runner.task_group(exception_in_result=True) as tg:
        tg.add_task(1, task, 1, tid=1)
        tg.add_task(2, error, 2)
        tg.add_task(3, atask, 3, tid=3)

    assert tg.results[1] == (1, 1)
    assert tg.results[3] == (3, 3)

    assert isinstance(tg.results[2], ValueError)
    assert tg.results[2].args[0] == 2

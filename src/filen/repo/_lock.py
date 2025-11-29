from typing import ClassVar, Final, Literal, TypedDict
import asyncio
import threading
import time
from uuid import NAMESPACE_OID, uuid5

from filen._logging import logger
from filen.api.v3.models.user import LockRequestData

from ._base import AsyncRepoBase, LockResource, RepoBase

MAX_TRIES: Final = 100_000
TRY_INTERVAL: Final = 1.0  # sec
REFRESH_INTERVAL: Final = 5.0  # sec


class LockSharedState(TypedDict):
    mutex: threading.Lock
    count: int
    refresh_thread: threading.Thread | None
    stop_event: threading.Event


class AsyncLockSharedState(TypedDict):
    mutex: asyncio.Lock
    count: int
    refresh_task: asyncio.Task | None


class Lock(RepoBase):
    """Filen server-based lock for exclusive access to resources between different clients and applications"""

    _shared_state_lock: ClassVar[threading.Lock] = threading.Lock()
    _shared_state: ClassVar[dict[str, LockSharedState]] = {}

    def __init__(self, context, api, runner, resource: LockResource) -> None:
        super().__init__(context, api, runner)
        self._resource = resource
        self._lock_uuid = uuid5(NAMESPACE_OID, resource)
        self._max_tries = MAX_TRIES
        self._try_interval = TRY_INTERVAL

        logger.debug('Lock instance created: %s | %s', self._resource, self._lock_uuid)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def acquire(self):
        """Acquire resource lock"""

        state = self._get_or_create_state()

        with state['mutex']:
            state['count'] += 1
            if state['count'] > 1:
                logger.debug('Lock for %r already held, incrementing count to %d', self._resource, state['count'])
                return

            logger.debug('Attempting to acquire server lock for %r...', self._resource)

            if state['refresh_thread'] and state['refresh_thread'].is_alive():
                state['stop_event'].set()
                state['refresh_thread'].join()

            state['stop_event'].clear()

            tries = 0
            while tries < self._max_tries:
                response = self._api.v3.user.lock(
                    LockRequestData(
                        uuid=self._lock_uuid,
                        resource=self._resource,
                        type='acquire',
                    ),
                )

                if response.data.acquired:
                    logger.info('Server lock for %r acquired.', self._resource)
                    state['refresh_thread'] = threading.Thread(target=self._refresh_loop, daemon=True)
                    state['refresh_thread'].start()
                    return

                tries += 1
                time.sleep(self._try_interval)

            state['count'] -= 1
            raise TimeoutError(
                f'Could not acquire lock for resource {self._resource!r}. Max tries ({self._max_tries}) reached.'
            )

    def release(self):
        """Release lock"""

        state = self._get_or_create_state()

        with state['mutex']:
            if state['count'] == 0:
                return
            state['count'] -= 1
            if state['count'] > 0:
                logger.debug('Decremented lock count for %r to %d', self._resource, state['count'])
                return

            logger.debug('Releasing server lock for %r...', self._resource)
            if state['refresh_thread']:
                state['stop_event'].set()
                state['refresh_thread'].join()
                state['refresh_thread'] = None

            try:
                response = self._api.v3.user.lock(
                    LockRequestData(uuid=self._lock_uuid, resource=self._resource, type='release')
                )

                if not response.data.released:
                    raise RuntimeError(f'Server failed to release lock for resource {self._resource!r}')
                logger.info('Server lock for %r released.', self._resource)
            except Exception as err:
                state['count'] += 1
                logger.error('Failed to release lock for resource %r: %s', self._resource, err, exc_info=True)

    def status(self) -> Literal['locked'] | None:
        """Return lock status"""

        response = self._api.v3.user.lock(
            LockRequestData(uuid=self._lock_uuid, resource=self._resource, type='status'),
        )
        return response.data.status

    def _get_or_create_state(self) -> LockSharedState:
        with self._shared_state_lock:
            if self._resource not in Lock._shared_state:
                self._shared_state[self._resource] = {
                    'mutex': threading.Lock(),
                    'count': 0,
                    'refresh_thread': None,
                    'stop_event': threading.Event(),
                }
            return self._shared_state[self._resource]

    def _refresh_loop(self):
        state = self._get_or_create_state()
        while not state['stop_event'].wait(REFRESH_INTERVAL):
            with state['mutex']:
                try:
                    if state['count'] > 0:
                        self._api.v3.user.lock(
                            LockRequestData(uuid=self._lock_uuid, resource=self._resource, type='refresh')
                        )
                except Exception as err:
                    logger.error('Failed to refresh lock for resource %r: %s', self._resource, err, exc_info=True)


class AsyncLock(AsyncRepoBase):
    """Async Filen server-based lock for exclusive access. Re-entrant within a single process."""

    _shared_state_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _shared_state: ClassVar[dict[str, AsyncLockSharedState]] = {}

    def __init__(self, context, api, runner, resource: LockResource) -> None:
        super().__init__(context, api, runner)
        self._resource = resource
        self._lock_uuid = uuid5(NAMESPACE_OID, resource)
        self._max_tries = MAX_TRIES
        self._try_interval = TRY_INTERVAL
        logger.debug('AsyncLock instance created: %s | %s', self._resource, self._lock_uuid)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()

    async def acquire(self):
        """Acquire resource lock"""

        state = await self._get_or_create_state()

        async with state['mutex']:
            state['count'] += 1
            if state['count'] > 1:
                logger.debug('AsyncLock for %r already held, count: %d', self._resource, state['count'])
                return

            logger.debug('Attempting to acquire async server lock for %r...', self._resource)
            if state['refresh_task'] and not state['refresh_task'].done():
                state['refresh_task'].cancel()
                await asyncio.sleep(0)

            tries = 0
            while tries < self._max_tries:
                response = await self._api.v3.user.lock(
                    LockRequestData(uuid=self._lock_uuid, resource=self._resource, type='acquire')
                )
                if response.data.acquired:
                    logger.info('Async server lock for %r acquired.', self._resource)
                    state['refresh_task'] = asyncio.create_task(self._refresh_loop())
                    return
                tries += 1
                await asyncio.sleep(self._try_interval)

            state['count'] -= 1
            raise TimeoutError(
                f'Could not acquire async lock for {self._resource!r}. Max tries ({self._max_tries}) reached.'
            )

    async def release(self):
        """Release lock"""
        state = await self._get_or_create_state()
        async with state['mutex']:
            if state['count'] == 0:
                return

            state['count'] -= 1
            if state['count'] > 0:
                logger.debug('Decremented async lock count for %r to %d', self._resource, state['count'])
                return

            logger.debug('Releasing async server lock for %r...', self._resource)
            if state['refresh_task']:
                state['refresh_task'].cancel()
                state['refresh_task'] = None

            try:
                response = await self._api.v3.user.lock(
                    LockRequestData(uuid=self._lock_uuid, resource=self._resource, type='release')
                )
                if not response.data.released:
                    raise RuntimeError(f'Server failed to release async lock for {self._resource!r}')
                logger.info('Async server lock for %r released.', self._resource)
            except Exception as err:
                state['count'] += 1
                logger.error('Failed to release async lock for %r: %s', self._resource, err, exc_info=True)

    async def status(self) -> Literal['locked'] | None:
        """Return lock status"""
        response = await self._api.v3.user.lock(
            LockRequestData(uuid=self._lock_uuid, resource=self._resource, type='status')
        )
        return response.data.status

    async def _get_or_create_state(self) -> AsyncLockSharedState:
        async with self._shared_state_lock:
            if self._resource not in self._shared_state:
                self._shared_state[self._resource] = {
                    'mutex': asyncio.Lock(),
                    'count': 0,
                    'refresh_task': None,
                }
            return self._shared_state[self._resource]

    async def _refresh_loop(self):
        state = await self._get_or_create_state()
        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            async with state['mutex']:
                try:
                    if state['count'] > 0:
                        await self._api.v3.user.lock(
                            LockRequestData(uuid=self._lock_uuid, resource=self._resource, type='refresh')
                        )
                except Exception as err:
                    logger.error('Failed to refresh async lock for %r: %s', self._resource, err, exc_info=True)

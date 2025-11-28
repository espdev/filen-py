from typing import Self, Type
from abc import ABC, abstractmethod

from httpx import AsyncClient, Client, Limits, Timeout

from filen._context import Context
from filen._logging import logger
from filen.api import AsyncFilenAPI, FilenAPI
from filen.config import DEFAULT_CONCURRENCY, DEFAULT_MAX_KEEPALIVE_CONNECTIONS, FilenConfig
from filen.errors import FilenError
from filen.repo import AsyncEnsureContextMixIn, AsyncRepoBase, EnsureContextMixIn, RepoBase, RepoFactoryMixIn
from filen.runners import AsyncRunnerBase, AsyncThreadRunner, RunnerBase, ThreadRunner


class FilenClientGenericBase[
    TClient: Client | AsyncClient,
    TAPI: FilenAPI | AsyncFilenAPI,
    TRepo: RepoBase | AsyncRepoBase,
    TRunner: RunnerBase | AsyncRunnerBase,
](ABC):
    """Base generic repository class (facade) for Filen sync/async clients"""

    def __init__(
        self,
        config: FilenConfig | None = None,
        *,
        runner: TRunner | None = None,
        http_client: TClient | None = None,
    ) -> None:
        config = config or FilenConfig()
        self._context = Context.create_from_config(config)

        self._runner = runner or self._create_default_runner()
        self._owns_runner = runner is None

        self._http_client = http_client or self._create_client(config)
        self._owns_http_client = http_client is None

        self._api = self._create_api()

    @property
    def is_closed(self) -> bool:
        return self._http_client.is_closed  # noqa

    @property
    def is_valid_context(self) -> bool:
        return self._context.is_valid

    @property
    def timeout(self) -> Timeout:
        return self._http_client.timeout  # noqa

    @abstractmethod
    def _create_default_runner(self) -> TRunner:
        pass

    @abstractmethod
    def _create_client(self, config: FilenConfig) -> TClient:
        pass

    @abstractmethod
    def _create_api(self) -> TAPI:
        pass

    def _create_repo(self, repo_type: Type[TRepo]) -> TRepo:
        return repo_type(context=self._context, api=self._api, runner=self._runner)


class FilenClientBase(
    FilenClientGenericBase[Client, FilenAPI, RepoBase, RunnerBase],
    EnsureContextMixIn,
    RepoFactoryMixIn,
):
    """Base class for Filen sync clients"""

    def ensure_context(self, raise_err: bool = True) -> bool:
        try:
            self._ensure_context()
        except FilenError as err:
            if raise_err:
                raise
            logger.debug('Unable to ensure context: %s', err, exc_info=err)
        return self.is_valid_context

    def close(self) -> None:
        if self._owns_runner:
            self._runner.shutdown()
        if self._owns_http_client:
            self._http_client.close()

    def _create_default_runner(self) -> RunnerBase:
        return ThreadRunner()

    def _create_client(self, config: FilenConfig) -> Client:
        return Client(
            timeout=config.request_timeout,
            limits=Limits(
                max_connections=config.max_connections,
                max_keepalive_connections=min(DEFAULT_MAX_KEEPALIVE_CONNECTIONS, config.max_connections),
            ),
        )

    def _create_api(self) -> FilenAPI:
        return FilenAPI(self._context, self._http_client)

    def __enter__(self) -> Self:
        if self._owns_http_client:
            self._http_client.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        if self._owns_runner:
            self._runner.shutdown()
        if self._owns_http_client:
            return self._http_client.__exit__(exc_type, exc_val, exc_tb)
        return None


class AsyncFilenClientBase(
    FilenClientGenericBase[AsyncClient, AsyncFilenAPI, AsyncRepoBase, AsyncRunnerBase],
    AsyncEnsureContextMixIn,
    RepoFactoryMixIn,
):
    """Base class for Filen async clients"""

    async def ensure_context(self, raise_err: bool = True) -> bool:
        try:
            await self._ensure_context()
        except FilenError as err:
            if raise_err:
                raise
            logger.debug('Unable to ensure context: %s', err, exc_info=err)
        return self.is_valid_context

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    def _create_default_runner(self) -> AsyncRunnerBase:
        return AsyncThreadRunner(concurrency=DEFAULT_CONCURRENCY)

    def _create_client(self, config: FilenConfig) -> AsyncClient:
        return AsyncClient(
            timeout=config.request_timeout,
            limits=Limits(
                max_connections=config.max_connections,
                max_keepalive_connections=min(DEFAULT_MAX_KEEPALIVE_CONNECTIONS, config.max_connections),
            ),
        )

    def _create_api(self) -> AsyncFilenAPI:
        return AsyncFilenAPI(self._context, self._http_client)

    async def __aenter__(self) -> Self:
        if self._owns_http_client:
            await self._http_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        if self._owns_http_client:
            return await self._http_client.__aexit__(exc_type, exc_val, exc_tb)
        return None

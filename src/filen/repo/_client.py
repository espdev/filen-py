from typing import Self
from abc import abstractmethod

from httpx import AsyncClient, Client

from filen.api import AsyncFilenAPI, FilenAPI
from filen.runners import AsyncRunnerBase, AsyncThreadRunner, RunnerBase, ThreadRunner

from ._base import AsyncRepo, FilenClientRepoBase, Repo


class FilenClientRepo(FilenClientRepoBase[Client, FilenAPI, Repo, RunnerBase]):
    def _create_default_runner(self) -> RunnerBase:
        return ThreadRunner()

    def _create_client(self) -> Client:
        return Client(base_url=self._context.api_url)

    def _create_api(self) -> FilenAPI:
        return FilenAPI(self._context, self._http_client)

    @abstractmethod
    def update_context(self) -> bool:
        pass

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


class AsyncFilenClientRepo(FilenClientRepoBase[AsyncClient, AsyncFilenAPI, AsyncRepo, AsyncRunnerBase]):
    def _create_default_runner(self) -> AsyncRunnerBase:
        return AsyncThreadRunner()

    def _create_client(self) -> AsyncClient:
        return AsyncClient(base_url=self._context.api_url)

    def _create_api(self) -> AsyncFilenAPI:
        return AsyncFilenAPI(self._context, self._http_client)

    @abstractmethod
    async def update_context(self) -> bool:
        pass

    async def __aenter__(self) -> Self:
        if self._owns_http_client:
            await self._http_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        if self._owns_http_client:
            return await self._http_client.__aexit__(exc_type, exc_val, exc_tb)
        return None

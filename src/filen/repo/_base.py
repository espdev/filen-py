from typing import Self, Type
from abc import ABC, abstractmethod

from httpx import AsyncClient, Client, Timeout

from filen.api import AsyncFilenAPI, FilenAPI
from filen.config import FilenConfig
from filen.errors import NoMasterKeysError
from filen.runners import AsyncRunnerBase, RunnerBase

type TimeoutType = Timeout | float | tuple[float, float, float, float]


class Unset: ...


UNSET = Unset()


class RepoBase[TFilenAPI: FilenAPI | AsyncFilenAPI, TRunner: RunnerBase | AsyncRunnerBase]:
    """Base generic class for all sync/async repository classes"""

    def __init__(self, config: FilenConfig, api: TFilenAPI, runner: TRunner) -> None:
        self._config = config
        self._api = api
        self._runner = runner

    @property
    def _current_master_key(self) -> str:
        if not self._config.master_keys:
            raise NoMasterKeysError('There are no master keys.')
        return self._config.master_keys[-1].get_secret_value()

    @property
    def _master_keys(self) -> list[str]:
        if not self._config.master_keys:
            raise NoMasterKeysError('There are no master keys.')
        return [key.get_secret_value() for key in self._config.master_keys]


class Repo(RepoBase[FilenAPI, RunnerBase]):
    """Repository base class for all sync repository classes"""


class AsyncRepo(RepoBase[AsyncFilenAPI, AsyncRunnerBase]):
    """Repository base class for all async repository classes"""


class FilenClientRepoBase[
    TClient: Client | AsyncClient,
    TAPI: FilenAPI | AsyncFilenAPI,
    TRepo: Repo | AsyncRepo,
    TRunner: RunnerBase | AsyncRunnerBase,
](ABC):
    """Base generic repository class (facade) for Filen sync/async clients"""

    def __init__(
        self,
        config: FilenConfig | None = None,
        *,
        runner: TRunner | None = None,
        http_client: TClient | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
    ) -> None:
        self._config = config.model_copy() if config else FilenConfig()

        self._runner = runner or self._create_default_runner()
        self._owns_runner = runner is None

        self._http_client = http_client or self._create_client()
        self._owns_http_client = http_client is None

        if not self._owns_http_client:
            self._http_client.base_url = str(self._config.api_url)

        if timeout is not UNSET:
            self._http_client.timeout = timeout

        self._api = self._create_api()

    @property
    def config(self) -> FilenConfig:
        return self._config

    @property
    def timeout(self) -> Timeout:
        return self._http_client.timeout  # noqa

    @property
    def closed(self) -> bool:
        return self._http_client.is_closed  # noqa

    @abstractmethod
    def _create_default_runner(self) -> TRunner:
        pass

    @abstractmethod
    def _create_client(self) -> TClient:
        pass

    @abstractmethod
    def _create_api(self) -> TAPI:
        pass

    def _create_repo(self, repo_type: Type[TRepo]) -> TRepo:
        return repo_type(config=self._config, api=self._api, runner=self._runner)


class _RepoDescriptor[TRepo: Repo | AsyncRepo]:
    """Generic descriptor initializes and caches repository instances in Filen client sync/async classes."""

    def __init__(self, repo_type: Type[TRepo]) -> None:
        self._repo_type = repo_type
        self._repos: dict[int, TRepo] = {}

    def __get__(
        self,
        client: FilenClientRepoBase | None,
        client_type: Type[FilenClientRepoBase] | None = None,
    ) -> TRepo | Self:
        if client is None:
            return self

        # The descriptor can be used with several client instances
        _id = id(client)

        if _id not in self._repos:
            self._repos[_id] = client._create_repo(self._repo_type)  # noqa

        return self._repos[_id]


repo = _RepoDescriptor[Repo]
"""Repository descriptor for creating repositories in sync Filen client"""

async_repo = _RepoDescriptor[AsyncRepo]
"""Repository descriptor for creating repositories in async Filen client"""

from typing import TYPE_CHECKING, Optional, Self, Type

from filen.api import AsyncFilenAPI, FilenAPI
from filen.config import FilenConfig
from filen.runners import AsyncRunnerBase, RunnerBase

if TYPE_CHECKING:
    from filen._client import FilenClientBase


class RepoBase[TFilenAPI: FilenAPI | AsyncFilenAPI, TRunner: RunnerBase | AsyncRunnerBase]:
    """Base class for all sync/async repository classes"""

    def __init__(self, config: FilenConfig, api: TFilenAPI, runner: TRunner) -> None:
        self._config = config
        self._api = api
        self._runner = runner


class Repo(RepoBase[FilenAPI, RunnerBase]): ...


class AsyncRepo(RepoBase[AsyncFilenAPI, AsyncRunnerBase]): ...


class _RepoDescriptor[TRepo: Repo | AsyncRepo]:
    """Repo descriptor

    To automatically initialize repository instances in the client.
    """

    def __init__(self, repo_type: Type[TRepo]) -> None:
        self._repo_type = repo_type
        self._repo: dict[int, TRepo] = {}

    def __get__(
        self,
        client: Optional['FilenClientBase'],
        client_type: Type['FilenClientBase'] | None = None,
    ) -> TRepo | Self:
        if client is None:
            return self

        # The descriptor can be used with several client instances
        cid = id(client)

        if cid not in self._repo:
            self._repo[cid] = self._repo_type(
                config=client.config,
                api=client._api,  # noqa
                runner=client._runner,  # noqa
            )

        return self._repo[cid]


repo = _RepoDescriptor[Repo | AsyncRepo]

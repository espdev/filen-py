from typing import Self
from abc import ABC, abstractmethod

from httpx import AsyncClient, Client, Timeout

from filen.api import AsyncFilenAPI, FilenAPI
from filen.api.models.auth import NO_2FA_CODE_PLACEHOLDER
from filen.config import FilenConfig
from filen.repo import AsyncAuth, AsyncUser, Auth, User, repo
from filen.runners import AsyncRunnerBase, AsyncThreadRunner, RunnerBase, ThreadRunner

type TimeoutType = Timeout | float | tuple[float, float, float, float]


class Unset: ...


UNSET = Unset()


class FilenClientBase[
    TClient: Client | AsyncClient,
    TAPI: FilenAPI | AsyncFilenAPI,
    TRunner: RunnerBase | AsyncRunnerBase,
](ABC):
    """Base class for Filen sync/async clients"""

    _auth: Auth | AsyncAuth
    user: User | AsyncUser

    def __init__(
        self,
        config: FilenConfig | None = None,
        *,
        runner: TRunner | None = None,
        http_client: TClient | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
    ) -> None:
        self._config = config or FilenConfig()

        self._runner = runner or self._create_default_runner()
        self._ownes_runner = runner is None

        self._http_client = http_client or self._create_client()
        self._ownes_http_client = http_client is None

        if not self._ownes_http_client:
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


class FilenClient(FilenClientBase[Client, FilenAPI, RunnerBase]):
    """Filen client"""

    _auth: Auth = repo(Auth)
    user: User = repo(User)

    def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> None:
        self._auth.login(email, password, two_factor_code)

    def logged_in(self) -> bool:
        return self._auth.logged_in()

    def _create_default_runner(self) -> RunnerBase:
        return ThreadRunner()

    def _create_client(self) -> Client:
        return Client(base_url=str(self.config.api_url))

    def _create_api(self) -> FilenAPI:
        return FilenAPI(self._config, self._http_client)

    def __enter__(self) -> Self:
        if self._ownes_http_client:
            self._http_client.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        if self._ownes_runner:
            self._runner.shutdown()
        if self._ownes_http_client:
            return self._http_client.__exit__(exc_type, exc_val, exc_tb)
        return None


class AsyncFilenClient(FilenClientBase[AsyncClient, AsyncFilenAPI, AsyncRunnerBase]):
    """Filen async client"""

    _auth: AsyncAuth = repo(AsyncAuth)
    user: AsyncUser = repo(AsyncUser)

    async def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> None:
        await self._auth.login(email, password, two_factor_code)

    async def logged_in(self) -> bool:
        return await self._auth.logged_in()

    def _create_default_runner(self) -> AsyncRunnerBase:
        return AsyncThreadRunner()

    def _create_client(self) -> AsyncClient:
        return AsyncClient(base_url=str(self.config.api_url))

    def _create_api(self) -> AsyncFilenAPI:
        return AsyncFilenAPI(self._config, self._http_client)

    async def __aenter__(self) -> Self:
        if self._ownes_http_client:
            await self._http_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        if self._ownes_http_client:
            return await self._http_client.__aexit__(exc_type, exc_val, exc_tb)
        return None

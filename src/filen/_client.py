from typing import Self
from abc import ABC, abstractmethod
from contextlib import contextmanager

from httpx import AsyncClient, Client, Timeout

from filen.api import AsyncFilenAPI, FilenAPI
from filen.api.models.auth import NO_2FA_CODE_PLACEHOLDER, AuthInfoRequestData, LoginRequestData
from filen.api.models.user import UserInfoData
from filen.config import AuthVersion, FilenConfig
from filen.crypto import decrypt_metadata, derive_password_and_master_key
from filen.errors import FilenError, RequestFailedError
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

    supported_auth_versions = {AuthVersion.v2}

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
    def api(self) -> TAPI:
        return self._api

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

    def _check_auth_version(self, auth_version: int):
        if auth_version not in self.supported_auth_versions:
            raise FilenError(f'Unsupported auth version {auth_version}.')

    @contextmanager
    def _check_login(self):
        res = {'ok': self.config.is_valid_for_auth() and self.config.auth_version in self.supported_auth_versions}
        try:
            yield res
        except RequestFailedError as err:
            if err.code == 'invalid_params':
                res['ok'] = False
            else:
                raise


class FilenClient(FilenClientBase[Client, FilenAPI, RunnerBase]):
    """Filen client"""

    def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> None:
        auth_info = self.api.auth.info(AuthInfoRequestData(email=email))
        self._check_auth_version(auth_info.data.auth_version)

        derived_info = derive_password_and_master_key(password, auth_info.data.salt)

        login_info = self.api.auth.login(
            LoginRequestData(
                email=email,  # noqa
                password=derived_info.password,
                two_factor_code=two_factor_code,
                auth_version=auth_info.data.auth_version,
            ),
        )

        with self._runner.task_group() as gr:
            gr.add_task('master_keys', decrypt_metadata, login_info.data.master_keys, derived_info.master_key)
            gr.add_task('private_key', decrypt_metadata, login_info.data.private_key, derived_info.master_key)

        master_keys = gr.results['master_keys']
        private_key = gr.results['private_key']

        self.config.auth_version = auth_info.data.auth_version
        self.config.api_key = login_info.data.api_key
        self.config.master_keys = master_keys
        self.config.public_key = login_info.data.public_key
        self.config.private_key = private_key

    def logged_in(self) -> bool:
        with self._check_login() as res:
            if res['ok']:
                _ = self.user_info()
        return res['ok']

    def user_info(self) -> UserInfoData:
        return self.api.user.info().data

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

    async def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> None:
        auth_info = await self.api.auth.info(AuthInfoRequestData(email=email))
        self._check_auth_version(auth_info.data.auth_version)

        derived_info = await self._runner.run_sync(derive_password_and_master_key, password, auth_info.data.salt)

        login_info = await self.api.auth.login(
            LoginRequestData(
                email=email,  # noqa
                password=derived_info.password,
                two_factor_code=two_factor_code,
                auth_version=auth_info.data.auth_version,
            ),
        )

        async with self._runner.task_group() as gr:
            gr.add_task('master_keys', decrypt_metadata, login_info.data.master_keys, derived_info.master_key)
            gr.add_task('private_key', decrypt_metadata, login_info.data.private_key, derived_info.master_key)

        master_keys = gr.results['master_keys']
        private_key = gr.results['private_key']

        self.config.auth_version = auth_info.data.auth_version
        self.config.api_key = login_info.data.api_key
        self.config.master_keys = master_keys
        self.config.public_key = login_info.data.public_key
        self.config.private_key = private_key

    async def logged_in(self) -> bool:
        with self._check_login() as res:
            if res['ok']:
                _ = await self.user_info()
        return res['ok']

    async def user_info(self) -> UserInfoData:
        return (await self.api.user.info()).data

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

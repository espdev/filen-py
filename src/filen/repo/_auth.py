from contextlib import contextmanager

from filen._context import Context
from filen.api.models.auth import (
    NO_2FA_CODE_PLACEHOLDER,
    AuthInfo,
    AuthInfoRequestData,
    AuthVersion,
    LoginRequestData,
    UserKeys,
)
from filen.crypto import decrypt_master_keys, decrypt_metadata, derive_master_key_and_hashed_password
from filen.errors import FilenError, RequestFailedError

from ._base import AsyncRepo, Repo


class AuthMixIn:
    supported_auth_versions = {AuthVersion.v2}

    _context: Context

    def _check_auth_version(self, auth_version: int):
        if auth_version not in self.supported_auth_versions:
            raise FilenError(f'Unsupported auth version {auth_version}.')

    @contextmanager
    def _check_login(self):
        res = {
            'ok': (
                self._context.has_api_key()
                and (self._context.has_master_keys() or self._context.has_credentials())
                and self._context.auth_version in self.supported_auth_versions
            )
        }
        try:
            yield res
        except RequestFailedError as err:
            if err.code == 'invalid_params':
                res['ok'] = False
            else:
                raise


class Auth(AuthMixIn, Repo):
    """Auth repository"""

    def info(self, email: str) -> AuthInfo:
        auth_info = self._api.auth.info(AuthInfoRequestData(email=email))
        self._check_auth_version(auth_info.data.auth_version)
        return auth_info.data

    def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        """Login in Filen service with email/password and optionally 2FA TOTP code"""

        auth_info = self.info(email)
        derived_info = derive_master_key_and_hashed_password(password, auth_info.salt)

        login_info = self._api.auth.login(
            LoginRequestData(
                email=email,  # noqa
                password=derived_info.password,
                two_factor_code=two_factor_code,
                auth_version=auth_info.auth_version,
            ),
        ).data

        with self._runner.task_group() as gr:
            gr.add_task('master_keys', decrypt_master_keys, login_info.master_keys, derived_info.master_key)
            gr.add_task('private_key', decrypt_metadata, login_info.private_key, derived_info.master_key)

        master_keys = gr.results['master_keys']
        private_key = gr.results['private_key']

        self._context.auth_version = auth_info.auth_version
        self._context.api_key = login_info.api_key
        self._context.master_keys = master_keys
        self._context.public_key = login_info.public_key
        self._context.private_key = private_key
        self._context.user_id = auth_info.id

        return UserKeys(
            api_key=login_info.api_key,
            master_keys=master_keys,
            public_key=login_info.public_key,
            private_key=private_key,
        )

    def logged_in(self) -> bool:
        with self._check_login() as res:
            if res['ok']:
                _ = self._api.user.info()
        return res['ok']


class AsyncAuth(AuthMixIn, AsyncRepo):
    """Async auth repository"""

    async def info(self, email: str) -> AuthInfo:
        auth_info = await self._api.auth.info(AuthInfoRequestData(email=email))
        self._check_auth_version(auth_info.data.auth_version)
        return auth_info.data

    async def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        auth_info = await self.info(email)
        derived_info = await self._runner.run_sync(derive_master_key_and_hashed_password, password, auth_info.salt)

        login_info = (
            await self._api.auth.login(
                LoginRequestData(
                    email=email,  # noqa
                    password=derived_info.password,
                    two_factor_code=two_factor_code,
                    auth_version=auth_info.auth_version,
                ),
            )
        ).data

        async with self._runner.task_group() as gr:
            gr.add_task('master_keys', decrypt_master_keys, login_info.master_keys, derived_info.master_key)
            gr.add_task('private_key', decrypt_metadata, login_info.private_key, derived_info.master_key)

        master_keys = gr.results['master_keys']
        private_key = gr.results['private_key']

        self._context.auth_version = auth_info.auth_version
        self._context.api_key = login_info.api_key
        self._context.master_keys = master_keys
        self._context.public_key = login_info.public_key
        self._context.private_key = private_key
        self._context.user_id = auth_info.id

        return UserKeys(
            api_key=login_info.api_key,
            master_keys=master_keys,
            public_key=login_info.public_key,
            private_key=private_key,
        )

    async def logged_in(self) -> bool:
        with self._check_login() as res:
            if res['ok']:
                _ = await self._api.user.info()
        return res['ok']

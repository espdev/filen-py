from filen.api.models.auth import NO_2FA_CODE_PLACEHOLDER, UserKeys
from filen.repo import (
    AsyncAuth,
    AsyncDir,
    AsyncFilenClientBase,
    AsyncUser,
    Auth,
    Dir,
    FilenClientBase,
    User,
    async_repo,
    repo,
)


class FilenClient(FilenClientBase):
    """Filen client"""

    _auth: Auth = repo(Auth)
    user: User = repo(User)
    dir: Dir = repo(Dir)

    def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        return self._auth.login(email, password, two_factor_code)

    def logged_in(self) -> bool:
        return self._auth.logged_in()

    def ensure_context(self):
        """Ensure the client context info or raise an exception"""

        self.user.master_keys()
        self.user.key_pair()
        self.user.base_folder()


class AsyncFilenClient(AsyncFilenClientBase):
    """Filen async client"""

    _auth: AsyncAuth = async_repo(AsyncAuth)
    user: AsyncUser = async_repo(AsyncUser)
    dir: AsyncDir = async_repo(AsyncDir)

    async def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        return await self._auth.login(email, password, two_factor_code)

    async def logged_in(self) -> bool:
        return await self._auth.logged_in()

    async def ensure_context(self):
        """Ensure the client context info or raise an exception"""

        await self.user.master_keys()
        await self.user.key_pair()
        await self.user.base_folder()

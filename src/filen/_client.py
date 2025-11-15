from filen.api.models.auth import NO_2FA_CODE_PLACEHOLDER
from filen.repo import AsyncAuth, AsyncFilenClientRepo, AsyncUser, Auth, FilenClientRepo, User, async_repo, repo


class FilenClient(FilenClientRepo):
    """Filen client"""

    _auth: Auth = repo(Auth)
    user: User = repo(User)

    def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> None:
        self._auth.login(email, password, two_factor_code)

    def logged_in(self) -> bool:
        return self._auth.logged_in()


class AsyncFilenClient(AsyncFilenClientRepo):
    """Filen async client"""

    _auth: AsyncAuth = async_repo(AsyncAuth)
    user: AsyncUser = async_repo(AsyncUser)

    async def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> None:
        await self._auth.login(email, password, two_factor_code)

    async def logged_in(self) -> bool:
        return await self._auth.logged_in()

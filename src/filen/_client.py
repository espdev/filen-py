from filen._base import AsyncFilenClientBase, FilenClientBase
from filen.repo import FS, Account, AsyncAccount, AsyncFS, AsyncStorage, Storage, repo
from filen.repo.models import UserKeys


class FilenClient(FilenClientBase):
    """Filen client"""

    account: Account = repo(Account)
    storage: Storage = repo(Storage)
    fs: FS = repo(FS)

    def login(self, email: str, password: str, two_factor_code: str | None = None) -> UserKeys:
        return self.account.login(email, password, two_factor_code)

    def logged_in(self) -> bool:
        return self.account.logged_in()


class AsyncFilenClient(AsyncFilenClientBase):
    """Filen async client"""

    account: AsyncAccount = repo(AsyncAccount)
    storage: AsyncStorage = repo(AsyncStorage)
    fs: AsyncFS = repo(AsyncFS)

    async def login(self, email: str, password: str, two_factor_code: str | None = None) -> UserKeys:
        return await self.account.login(email, password, two_factor_code)

    async def logged_in(self) -> bool:
        return await self.account.logged_in()

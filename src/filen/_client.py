from filen._base import AsyncFilenClientBase, FilenClientBase
from filen.api.models.auth import NO_2FA_CODE_PLACEHOLDER, UserKeys
from filen.repo import Account, AsyncAccount, AsyncStorage, Storage, repo


class FilenClient(FilenClientBase):
    """Filen client"""

    account: Account = repo(Account)
    storage: Storage = repo(Storage)

    def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        return self.account.login(email, password, two_factor_code)

    def logged_in(self) -> bool:
        return self.account.logged_in()


class AsyncFilenClient(AsyncFilenClientBase):
    """Filen async client"""

    account: AsyncAccount = repo(AsyncAccount)
    storage: AsyncStorage = repo(AsyncStorage)

    async def login(self, email: str, password: str, two_factor_code: str = NO_2FA_CODE_PLACEHOLDER) -> UserKeys:
        return await self.account.login(email, password, two_factor_code)

    async def logged_in(self) -> bool:
        return await self.account.logged_in()

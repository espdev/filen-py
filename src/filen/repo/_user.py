from uuid import UUID

from filen.api.models.user import UserInfo, UserKeyPair, UserSettings

from ._base import AsyncRepoBase, RepoBase


class User(RepoBase):
    """User repository"""

    def info(self) -> UserInfo:
        return self._api.user.info().data

    def settings(self) -> UserSettings:
        return self._api.user.settings().data

    def base_folder(self) -> UUID:
        return self._ensure_base_folder_uuid()

    def master_keys(self) -> list[str]:
        """Retrieve user's master keys and update it in the context"""

        return self._ensure_master_keys()

    def key_pair(self) -> UserKeyPair:
        """Return user's decrypted public/private key pair"""

        return self._ensure_key_pair()


class AsyncUser(AsyncRepoBase):
    """Async user repository"""

    async def info(self) -> UserInfo:
        return (await self._api.user.info()).data

    async def settings(self) -> UserSettings:
        return (await self._api.user.settings()).data

    async def base_folder(self) -> UUID:
        return await self._ensure_base_folder_uuid()

    async def master_keys(self) -> list[str]:
        """Retrieve user's master keys"""

        return await self._ensure_master_keys()

    async def key_pair(self) -> UserKeyPair:
        """Return user's decrypted public/private key pair"""

        return await self._ensure_key_pair()

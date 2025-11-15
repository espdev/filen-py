from uuid import UUID

from filen.api.models.user import UserInfo, UserKeyPairInfo, UserSettings
from filen.crypto import decrypt_metadata

from ._base import AsyncRepo, Repo


class User(Repo):
    """User repository"""

    def info(self) -> UserInfo:
        return self._api.user.info().data

    def settings(self) -> UserSettings:
        return self._api.user.settings().data

    def base_folder(self) -> UUID:
        return self._api.user.base_folder().data.uuid

    def key_pair_info(self) -> UserKeyPairInfo:
        """Return user's decrypted public/private key pair"""

        key_pair_data = self._api.user.key_pair_info().data
        key_pair_data.private_key = decrypt_metadata(key_pair_data.private_key, self._master_keys)

        return key_pair_data


class AsyncUser(AsyncRepo):
    """Async user repository"""

    async def info(self) -> UserInfo:
        return (await self._api.user.info()).data

    async def settings(self) -> UserSettings:
        return (await self._api.user.settings()).data

    async def base_folder(self) -> UUID:
        return (await self._api.user.base_folder()).data.uuid

    async def key_pair_info(self) -> UserKeyPairInfo:
        """Return user's decrypted public/private key pair"""

        key_pair_data = (await self._api.user.key_pair_info()).data
        key_pair_data.private_key = await self._runner.run_sync(
            decrypt_metadata, key_pair_data.private_key, self._master_keys
        )

        return key_pair_data

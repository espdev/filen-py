from uuid import UUID

from filen.api.models.user import UserInfo, UserKeyPairInfo, UserMasterKeysRequestData, UserSettings
from filen.crypto import decrypt_master_keys, decrypt_metadata, encrypt_metadata

from ._base import AsyncRepo, Repo


class User(Repo):
    """User repository"""

    def info(self) -> UserInfo:
        return self._api.user.info().data

    def settings(self) -> UserSettings:
        return self._api.user.settings().data

    def base_folder(self) -> UUID:
        return self._api.user.base_folder().data.uuid

    def master_keys(self) -> list[str]:
        """Retrieve user's master keys"""

        master_key = self._latest_master_key
        master_key_enc = encrypt_metadata(master_key, master_key)
        master_keys_enc = self._api.user.master_keys(UserMasterKeysRequestData(master_keys=master_key_enc)).data.keys
        master_keys = decrypt_master_keys(master_keys_enc, master_key)

        return master_keys

    def key_pair(self) -> UserKeyPairInfo:
        """Return user's decrypted public/private key pair"""

        key_pair = self._api.user.key_pair_info().data
        key_pair.private_key = decrypt_metadata(key_pair.private_key, self._master_keys)

        return key_pair


class AsyncUser(AsyncRepo):
    """Async user repository"""

    async def info(self) -> UserInfo:
        return (await self._api.user.info()).data

    async def settings(self) -> UserSettings:
        return (await self._api.user.settings()).data

    async def base_folder(self) -> UUID:
        return (await self._api.user.base_folder()).data.uuid

    async def master_keys(self) -> list[str]:
        """Retrieve user's master keys"""

        master_key = self._latest_master_key
        master_key_enc = await self._runner.run_sync(encrypt_metadata, master_key, master_key)
        master_keys_enc = (
            await self._api.user.master_keys(UserMasterKeysRequestData(master_keys=master_key_enc))
        ).data.keys
        master_keys = await self._runner.run_sync(decrypt_master_keys, master_keys_enc, master_key)

        return master_keys

    async def key_pair(self) -> UserKeyPairInfo:
        """Return user's decrypted public/private key pair"""

        key_pair = (await self._api.user.key_pair_info()).data
        key_pair.private_key = await self._runner.run_sync(decrypt_metadata, key_pair.private_key, self._master_keys)

        return key_pair

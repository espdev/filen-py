from typing import Type
from uuid import UUID

from filen._context import Context
from filen._helpers import FactoryDescriptor
from filen.api import AsyncFilenAPI, FilenAPI
from filen.api.v3.models.auth import AuthInfoRequestData
from filen.api.v3.models.user import UserMasterKeysRequestData
from filen.crypto import decrypt_master_keys, decrypt_metadata, derive_master_key_and_hashed_password, encrypt_metadata
from filen.runners import AsyncRunnerBase, RunnerBase

from .models import UserKeyPair


class RepoGenericBase[TAPI: FilenAPI | AsyncFilenAPI, TRunner: RunnerBase | AsyncRunnerBase]:
    """Base generic class for all sync/async repository classes"""

    def __init__(self, context: Context, api: TAPI, runner: TRunner, /) -> None:
        self._context = context
        self._api = api
        self._runner = runner

    @property
    def is_closed(self) -> bool:
        return self._api.is_closed  # noqa


class RepoFactoryMixIn:
    _context: Context
    _api: FilenAPI | AsyncFilenAPI
    _runner: RunnerBase | AsyncRunnerBase

    def _create[TRepo: RepoGenericBase](self, repo_type: Type[TRepo], *args, **kwargs) -> TRepo:
        return repo_type(self._context, self._api, self._runner, *args, **kwargs)


class EnsureContextMixIn:
    _context: Context
    _api: FilenAPI
    _runner: RunnerBase

    def _ensure_master_keys(self) -> list[str]:
        """Ensure all user's master keus and cache it in the context or raise MasterKeysError"""

        if self._context.has_master_keys:
            return self._context.master_keys

        self._context.raise_for_inaccessible_keys()

        auth_info = self._api.v3.auth.info(AuthInfoRequestData(email=self._context.email)).data
        derived_info = derive_master_key_and_hashed_password(self._context.password, auth_info.salt)

        master_key_enc = encrypt_metadata(derived_info.master_key, derived_info.master_key)
        master_keys_enc = self._api.v3.user.master_keys(UserMasterKeysRequestData(master_keys=master_key_enc)).data.keys
        self._context.master_keys = decrypt_master_keys(master_keys_enc, derived_info.master_key)

        return self._context.master_keys

    def _ensure_master_key(self) -> str:
        """Ensure the current master key or raise InaccessibleKeysError"""

        self._ensure_master_keys()
        return self._context.current_master_key

    def _ensure_key_pair(self) -> UserKeyPair:
        """Ensure user's key pair and cache it in the context or raise InaccessibleKeysError"""

        if self._context.has_keypair:
            return UserKeyPair(
                public_key=self._context.public_key,
                private_key=self._context.private_key,
            )

        master_keys = self._ensure_master_keys()
        key_pair_info = self._api.v3.user.key_pair_info().data
        private_key = decrypt_metadata(key_pair_info.private_key, master_keys)

        self._context.public_key = key_pair_info.public_key
        self._context.private_key = private_key

        return UserKeyPair(
            public_key=self._context.public_key,
            private_key=self._context.private_key,
        )

    def _ensure_base_folder_uuid(self) -> UUID:
        """Ensure base folder directory UUID and cache it in the context"""

        if self._context.base_folder_uuid:
            return self._context.base_folder_uuid

        self._context.base_folder_uuid = self._api.v3.user.base_folder().data.uuid
        return self._context.base_folder_uuid

    def _ensure_context(self):
        self._ensure_master_keys()
        self._ensure_key_pair()
        self._ensure_base_folder_uuid()


class AsyncEnsureContextMixIn:
    _context: Context
    _api: AsyncFilenAPI
    _runner: AsyncRunnerBase

    async def _ensure_master_keys(self) -> list[str]:
        if self._context.has_master_keys:
            return self._context.master_keys

        self._context.raise_for_inaccessible_keys()

        auth_info = (await self._api.v3.auth.info(AuthInfoRequestData(email=self._context.email))).data
        derived_info = await self._runner.run_sync(
            derive_master_key_and_hashed_password, self._context.password, auth_info.salt
        )

        master_key_enc = await self._runner.run_sync(encrypt_metadata, derived_info.master_key, derived_info.master_key)
        master_keys_enc = (
            await self._api.v3.user.master_keys(UserMasterKeysRequestData(master_keys=master_key_enc))
        ).data.keys
        self._context.master_keys = await self._runner.run_sync(
            decrypt_master_keys, master_keys_enc, derived_info.master_key
        )

        return self._context.master_keys

    async def _ensure_master_key(self) -> str:
        await self._ensure_master_keys()
        return self._context.current_master_key

    async def _ensure_key_pair(self) -> UserKeyPair:
        """Ensure user's key pair or raise InaccessibleKeysError"""

        if self._context.has_keypair:
            return UserKeyPair(
                public_key=self._context.public_key,
                private_key=self._context.private_key,
            )

        master_keys = await self._ensure_master_keys()
        key_pair_info = (await self._api.v3.user.key_pair_info()).data
        private_key = await self._runner.run_sync(decrypt_metadata, key_pair_info.private_key, master_keys)

        self._context.public_key = key_pair_info.public_key
        self._context.private_key = private_key

        return UserKeyPair(
            public_key=self._context.public_key,
            private_key=self._context.private_key,
        )

    async def _ensure_base_folder_uuid(self) -> UUID:
        """Ensure base folder directory UUID and cache it in the context"""

        if self._context.base_folder_uuid:
            return self._context.base_folder_uuid

        self._context.base_folder_uuid = (await self._api.v3.user.base_folder()).data.uuid
        return self._context.base_folder_uuid

    async def _ensure_context(self):
        await self._ensure_master_keys()
        await self._ensure_key_pair()
        await self._ensure_base_folder_uuid()


class RepoBase(RepoGenericBase[FilenAPI, RunnerBase], EnsureContextMixIn, RepoFactoryMixIn):
    """Repository base class for all sync repository classes"""


class AsyncRepoBase(RepoGenericBase[AsyncFilenAPI, AsyncRunnerBase], AsyncEnsureContextMixIn, RepoFactoryMixIn):
    """Repository base class for all async repository classes"""


repo = FactoryDescriptor[RepoBase | AsyncRepoBase]

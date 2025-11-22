from typing import Final
import os
from uuid import UUID, uuid4

from filen.api.v3.models import StorageItemUUIDRequestData
from filen.api.v3.models.dir import (
    FileMetadata,
    FolderContent,
    FolderContentRequestData,
    FolderContentType,
    FolderCreated,
    FolderCreateRequestData,
    FolderDownload,
    FolderInfo,
    FolderItem,
    FolderMetadata,
)
from filen.api.v3.models.file import FileInfo
from filen.crypto import decrypt_metadata_model, encrypt_metadata_model, hash_name
from filen.errors import StorageError

from ._base import AsyncRepoBase, RepoBase

type ItemId = UUID | str

NAME_MAX_LEN: Final = 255


class StorageMixIn:
    @staticmethod
    def check_name(name: str) -> None:
        try:
            if not name:
                raise ValueError('empty name')
            if name in ('.', '..'):
                raise ValueError('. and .. not allowed')
            if '/' in name or '\\' in name or '\0' in name:
                raise ValueError('/, \\ and \\0 not allowed')
            try:
                max_len = os.pathconf('.', 'PC_NAME_MAX')
            except (AttributeError, ValueError):
                max_len = NAME_MAX_LEN
            if (name_len := len(name.encode())) > max_len:
                raise ValueError(f'name is too long in bytes ({name_len} > {max_len})')
        except ValueError as err:
            raise StorageError(f'Folder name {name!r} is not valid due to: {err}') from err

    @staticmethod
    def _decrypt_file_metadata(metadata: str, keys: str | list[str]) -> FileMetadata:
        return decrypt_metadata_model(FileMetadata, metadata, keys)

    @staticmethod
    def _decrypt_folder_metadata(metadata: str, keys: str | list[str]) -> FolderMetadata:
        return decrypt_metadata_model(FolderMetadata, metadata, keys)

    @staticmethod
    def _collect_decrypted_metadata[T: FolderContent | FolderDownload](
        folder_items: T,
        decryption_results: dict[tuple[FolderItem, int], str],
    ) -> T:
        for (t, i), metadata in decryption_results.items():
            match t:
                case FolderItem.file:
                    folder_items.files[i].metadata = metadata
                case FolderItem.folder:
                    folder_items.folders[i].metadata = metadata
        return folder_items


class Storage(RepoBase, StorageMixIn):
    """Storage repository

    Provides methods for manipulating with directories and files in the cloud storage.
    """

    def base_folder(self) -> UUID:
        """Retrieve the base foder UUID (root srorage UUID)"""

        return self._ensure_base_folder_uuid()

    def folder_info(self, uuid: ItemId | None = None) -> FolderInfo:
        """Retrieve folder info with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        folder_info = self._api.v3.dir.info(StorageItemUUIDRequestData(uuid=uuid)).data

        if uuid != self._context.base_folder_uuid:
            master_keys = self._ensure_master_keys()
            folder_info.metadata = self._decrypt_folder_metadata(folder_info.metadata, master_keys)
        else:
            folder_info.metadata = FolderMetadata(name='')
            folder_info.name_hashed = ''

        return folder_info

    def folder_content(self, uuid: ItemId | FolderContentType | None = None) -> FolderContent:
        """Retrieve folder content with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = self._ensure_master_keys()

        folder_content = self._api.v3.dir.content(FolderContentRequestData(uuid=uuid)).data

        with self._runner.task_group() as tg:
            for i, file in enumerate(folder_content.files):
                tg.add_task((FolderItem.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((FolderItem.folder, i), self._decrypt_folder_metadata, folder.metadata, master_keys)

        return self._collect_decrypted_metadata(folder_content, tg.results)

    def folder_download(self, uuid: ItemId | None = None) -> FolderDownload:
        """Retrieve folder tree (flattened) with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = self._ensure_master_keys()

        folder_download = self._api.v3.dir.download(StorageItemUUIDRequestData(uuid=uuid)).data

        with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task((FolderItem.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_download.folders):
                if folder.uuid != self._context.base_folder_uuid:
                    tg.add_task((FolderItem.folder, i), self._decrypt_folder_metadata, folder.metadata, master_keys)
                else:
                    folder.metadata = FolderMetadata(name='')
                    folder.name_hashed = ''

        return self._collect_decrypted_metadata(folder_download, tg.results)

    def create_folder(self, name: str, parent: UUID | None = None) -> FolderCreated:
        """Create a new folder in the cloud storage"""

        self.check_name(name)
        metadata = FolderMetadata(name=name)

        master_key = self._ensure_master_key()
        if parent is None:
            parent = self._ensure_base_folder_uuid()

        with self._runner.task_group() as tg:
            tg.add_task('metadata', encrypt_metadata_model, metadata, master_key)
            tg.add_task('name_hashed', hash_name, name, self._context.auth_version)

        metadata_enc = tg.results['metadata']
        name_hashed = tg.results['name_hashed']

        data = FolderCreateRequestData(
            uuid=uuid4(),
            name=metadata_enc,
            name_hashed=name_hashed,
            parent=parent,
        )
        return self._api.v3.dir.create(data).data

    def file_info(self, uuid: ItemId) -> FileInfo:
        """Return the file info"""

        master_keys = self._ensure_master_keys()

        file_info = self._api.v3.file.info(StorageItemUUIDRequestData(uuid=uuid)).data
        file_info.metadata = self._decrypt_file_metadata(file_info.metadata, master_keys)

        return file_info


class AsyncStorage(AsyncRepoBase, StorageMixIn):
    """Async Storage repository"""

    async def base_folder(self) -> UUID:
        return await self._ensure_base_folder_uuid()

    async def folder_info(self, uuid: ItemId | FolderContentType | None = None) -> FolderInfo:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        folder_info = (await self._api.v3.dir.info(StorageItemUUIDRequestData(uuid=uuid))).data

        if uuid != self._context.base_folder_uuid:
            master_keys = await self._ensure_master_keys()
            folder_info.metadata = await self._runner.run_sync(
                self._decrypt_folder_metadata, folder_info.metadata, master_keys
            )
        else:
            folder_info.metadata = FolderMetadata(name='')
            folder_info.name_hashed = ''

        return folder_info

    async def folder_content(self, uuid: ItemId | None = None) -> FolderContent:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        master_keys = await self._ensure_master_keys()

        folder_content = (await self._api.v3.dir.content(FolderContentRequestData(uuid=uuid))).data

        async with self._runner.task_group() as tg:
            for i, file in enumerate(folder_content.files):
                tg.add_task((FolderItem.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((FolderItem.folder, i), self._decrypt_folder_metadata, folder.metadata, master_keys)

        return self._collect_decrypted_metadata(folder_content, tg.results)

    async def folder_download(self, uuid: ItemId | None = None) -> FolderDownload:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        master_keys = await self._ensure_master_keys()

        folder_download = (await self._api.v3.dir.download(StorageItemUUIDRequestData(uuid=uuid))).data

        async with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task((FolderItem.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_download.folders):
                if folder.uuid != self._context.base_folder_uuid:
                    tg.add_task((FolderItem.folder, i), self._decrypt_folder_metadata, folder.metadata, master_keys)
                else:
                    folder.metadata = FolderMetadata(name='')
                    folder.name_hashed = ''

        return self._collect_decrypted_metadata(folder_download, tg.results)

    async def create_folder(self, name: str, parent: UUID | None = None) -> FolderCreated:
        self.check_name(name)
        metadata = FolderMetadata(name=name)

        master_key = await self._ensure_master_key()
        if parent is None:
            parent = await self._ensure_base_folder_uuid()

        async with self._runner.task_group() as tg:
            tg.add_task('metadata', encrypt_metadata_model, metadata, master_key)
            tg.add_task('name_hashed', hash_name, name, self._context.auth_version)

        metadata_enc = tg.results['metadata']
        name_hashed = tg.results['name_hashed']

        data = FolderCreateRequestData(
            uuid=uuid4(),
            name=metadata_enc,
            name_hashed=name_hashed,
            parent=parent,
        )
        return (await self._api.v3.dir.create(data)).data

    async def file_info(self, uuid: ItemId) -> FileInfo:
        master_keys = await self._ensure_master_keys()

        file_info = (await self._api.v3.file.info(StorageItemUUIDRequestData(uuid=uuid))).data
        file_info.metadata = await self._runner.run_sync(self._decrypt_file_metadata, file_info.metadata, master_keys)

        return file_info

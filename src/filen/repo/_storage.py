from typing import Final
import os
from urllib.parse import quote
from uuid import UUID, uuid4

from filen._context import Context
from filen.api.v3.models import StorageItemExistsRequestData, StorageItemUUIDRequestData
from filen.api.v3.models.dir import (
    FolderContentRequestData,
    FolderContentType,
    FolderCreateRequestData,
    FolderItemType,
)
from filen.config import FILEN_PUBLIC_FILE_LINK_BASE_URL, FILEN_PUBLIC_FOLDER_LINK_BASE_URL
from filen.crypto import decrypt_metadata, decrypt_metadata_model, encrypt_metadata_model, hash_name
from filen.errors import StorageError

from ._base import AsyncRepoBase, RepoBase
from .models import (
    CreateFolderInfo,
    FileInfo,
    FileMetadata,
    FolderContent,
    FolderInfo,
    FolderMetadata,
    PublicLinkStatus,
    StorageItemExists,
    StorageItemType,
)

type ItemId = UUID | str

NAME_MAX_LEN: Final = 255


class StorageMixIn:
    _context: Context

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

    def _decrypt_file_metadata(self, metadata: str, keys: str | list[str]) -> tuple[FileMetadata, str]:
        metadata = decrypt_metadata_model(FileMetadata, metadata, keys)
        name_hashed = hash_name(metadata.name, self._context.auth_version)
        return metadata, name_hashed

    def _decrypt_folder_metadata(self, metadata: str, keys: str | list[str]) -> tuple[FolderMetadata, str]:
        metadata = decrypt_metadata_model(FolderMetadata, metadata, keys)
        name_hashed = hash_name(metadata.name, self._context.auth_version)
        return metadata, name_hashed

    @staticmethod
    def _collect_folder_content(files_info, folders_info, decryption_results, trash: bool = False) -> FolderContent:
        files = []
        folders = []

        for (t, i), (metadata, name_hashed) in sorted(decryption_results.items(), key=lambda item: item[0][1]):
            match t:
                case FolderItemType.file:
                    file_info = files_info[i].model_dump(exclude={'metadata'})
                    file_info['metadata'] = metadata
                    file_info['name_hashed'] = file_info.get('name_hashed', name_hashed)
                    file_info['trash'] = file_info.get('trash', trash)
                    files.append(FileInfo.model_validate(file_info))

                case FolderItemType.folder:
                    folder_info = folders_info[i].model_dump(exclude={'name'})
                    folder_info['name'] = metadata.name
                    folder_info['name_hashed'] = folder_info.get('name_hashed', name_hashed)
                    folder_info['trash'] = folder_info.get('trash', trash)
                    folders.append(FolderInfo.model_validate(folder_info))

        return FolderContent(
            files=files,
            folders=folders,
        )


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

        if str(uuid) != str(self._context.base_folder_uuid):
            master_keys = self._ensure_master_keys()
            metadata, _ = self._decrypt_folder_metadata(folder_info.name_encrypted, master_keys)
        else:
            metadata = FolderMetadata(name='')

        folder_info_data = folder_info.model_dump()
        folder_info_data['name'] = metadata.name

        return FolderInfo.model_validate(folder_info_data)

    def folder_content(self, uuid: ItemId | FolderContentType | None = None) -> FolderContent:
        """Retrieve folder content with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = self._ensure_master_keys()

        folder_content = self._api.v3.dir.content(FolderContentRequestData(uuid=uuid)).data

        with self._runner.task_group() as tg:
            for i, file in enumerate(folder_content.uploads):
                tg.add_task((FolderItemType.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((FolderItemType.folder, i), self._decrypt_folder_metadata, folder.name, master_keys)

        trash = uuid == FolderContentType.trash
        return self._collect_folder_content(folder_content.uploads, folder_content.folders, tg.results, trash=trash)

    def folder_download(self, uuid: ItemId | None = None) -> FolderContent:
        """Retrieve folder tree (flattened) with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = self._ensure_master_keys()

        folder_download = self._api.v3.dir.download(StorageItemUUIDRequestData(uuid=uuid)).data

        with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task((FolderItemType.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_download.folders):
                if folder.uuid != self._context.base_folder_uuid:
                    tg.add_task((FolderItemType.folder, i), self._decrypt_folder_metadata, folder.name, master_keys)
                else:
                    folder.metadata = ''
                    folder.name_hashed = ''

        return self._collect_folder_content(folder_download.files, folder_download.folders, tg.results)

    def folder_exists(self, name: str, parent: UUID | None = None) -> StorageItemExists:
        """Check if a forlder exists"""

        if parent is None:
            parent = self._ensure_base_folder_uuid()

        name_hashed = hash_name(name, self._context.auth_version)

        return self._api.v3.dir.exists(
            StorageItemExistsRequestData(parent=parent, name_hashed=name_hashed),
        ).data_as(StorageItemExists, type=StorageItemType.folder)

    def create_folder(self, name: str, parent: UUID | None = None) -> CreateFolderInfo:
        """Create a new folder in the cloud storage"""

        self.check_name(name)
        master_key = self._ensure_master_key()

        metadata = FolderMetadata(name=name)
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
        return self._api.v3.dir.create(data).data_as(CreateFolderInfo)

    def file_exists(self, name: str, parent: UUID | None = None) -> StorageItemExists:
        """Check if a file exists"""

        if parent is None:
            parent = self._ensure_base_folder_uuid()

        name_hashed = hash_name(name, self._context.auth_version)

        return self._api.v3.file.exists(
            StorageItemExistsRequestData(parent=parent, name_hashed=name_hashed),
        ).data_as(StorageItemExists, type=StorageItemType.file)

    def file_info(self, uuid: ItemId) -> FileInfo:
        """Return the file info"""

        master_keys = self._ensure_master_keys()

        file_info = self._api.v3.file.info(StorageItemUUIDRequestData(uuid=uuid)).data
        metadata, _ = self._decrypt_file_metadata(file_info.metadata, master_keys)

        return FileInfo(**file_info.model_dump(exclude={'metadata'}), metadata=metadata)

    def link_status(self, uuid: ItemId, link_type: StorageItemType | str | None = None) -> PublicLinkStatus:
        data = StorageItemUUIDRequestData(uuid=uuid)

        match link_type:
            case StorageItemType.file:
                response = self._api.v3.file.link_status(data)
            case StorageItemType.folder:
                response = self._api.v3.dir.link_status(data)
            case _:
                response = self._api.v3.file.link_status(data)
                if response.data:
                    link_type = StorageItemType.file
                else:
                    response = self._api.v3.dir.link_status(data)
                    link_type = StorageItemType.folder

        if not response.data or not response.data.exists:
            return PublicLinkStatus.not_exist()

        if link_type == StorageItemType.file:
            file_info = self.file_info(uuid)
            key = file_info.metadata.key
            link_base_url = FILEN_PUBLIC_FILE_LINK_BASE_URL
        else:
            master_keys = self._ensure_master_keys()
            key = decrypt_metadata(response.data.key, master_keys)
            link_base_url = FILEN_PUBLIC_FOLDER_LINK_BASE_URL

        link_path = quote(f'{response.data.uuid}#{key}')
        link = f'{link_base_url}/{link_path}'

        return response.data_as(PublicLinkStatus, type=link_type, key=key, link=link)


class AsyncStorage(AsyncRepoBase, StorageMixIn):
    """Async Storage repository"""

    async def base_folder(self) -> UUID:
        return await self._ensure_base_folder_uuid()

    async def folder_info(self, uuid: ItemId | None = None) -> FolderInfo:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        folder_info = (await self._api.v3.dir.info(StorageItemUUIDRequestData(uuid=uuid))).data

        if str(uuid) != str(self._context.base_folder_uuid):
            master_keys = await self._ensure_master_keys()
            metadata, _ = await self._runner.run_sync(
                self._decrypt_folder_metadata, folder_info.name_encrypted, master_keys
            )
        else:
            metadata = FolderMetadata(name='')

        folder_info_data = folder_info.model_dump()
        folder_info_data['name'] = metadata.name

        return FolderInfo.model_validate(folder_info_data)

    async def folder_content(self, uuid: ItemId | FolderContentType | None = None) -> FolderContent:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        master_keys = await self._ensure_master_keys()

        folder_content = (await self._api.v3.dir.content(FolderContentRequestData(uuid=uuid))).data

        async with self._runner.task_group() as tg:
            for i, file in enumerate(folder_content.uploads):
                tg.add_task((FolderItemType.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_content.folders):
                tg.add_task((FolderItemType.folder, i), self._decrypt_folder_metadata, folder.name, master_keys)

        trash = uuid == FolderContentType.trash
        return self._collect_folder_content(folder_content.uploads, folder_content.folders, tg.results, trash=trash)

    async def folder_download(self, uuid: ItemId | None = None) -> FolderContent:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        master_keys = await self._ensure_master_keys()

        folder_download = (await self._api.v3.dir.download(StorageItemUUIDRequestData(uuid=uuid))).data

        async with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task((FolderItemType.file, i), self._decrypt_file_metadata, file.metadata, master_keys)

            for i, folder in enumerate(folder_download.folders):
                if folder.uuid != self._context.base_folder_uuid:
                    tg.add_task((FolderItemType.folder, i), self._decrypt_folder_metadata, folder.name, master_keys)
                else:
                    folder.name = ''
                    folder.name_hashed = ''

        return self._collect_folder_content(folder_download.files, folder_download.folders, tg.results)

    async def folder_exists(self, name: str, parent: UUID | None = None) -> StorageItemExists:
        if parent is None:
            parent = await self._ensure_base_folder_uuid()

        name_hashed = await self._runner.run_sync(hash_name, name, self._context.auth_version)

        return (
            await self._api.v3.dir.exists(StorageItemExistsRequestData(parent=parent, name_hashed=name_hashed))
        ).data_as(StorageItemExists, type=StorageItemType.folder)

    async def create_folder(self, name: str, parent: UUID | None = None) -> CreateFolderInfo:
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
        return (await self._api.v3.dir.create(data)).data_as(CreateFolderInfo)

    async def file_exists(self, name: str, parent: UUID | None = None) -> StorageItemExists:
        if parent is None:
            parent = await self._ensure_base_folder_uuid()

        name_hashed = await self._runner.run_sync(hash_name, name, self._context.auth_version)

        return (
            await self._api.v3.file.exists(StorageItemExistsRequestData(parent=parent, name_hashed=name_hashed))
        ).data_as(StorageItemExists, type=StorageItemType.file)

    async def file_info(self, uuid: ItemId) -> FileInfo:
        master_keys = await self._ensure_master_keys()

        file_info = (await self._api.v3.file.info(StorageItemUUIDRequestData(uuid=uuid))).data
        metadata, _ = await self._runner.run_sync(self._decrypt_file_metadata, file_info.metadata, master_keys)

        return FileInfo(**file_info.model_dump(exclude={'metadata'}), metadata=metadata)

    async def link_status(self, uuid: ItemId, link_type: StorageItemType | str | None = None) -> PublicLinkStatus:
        data = StorageItemUUIDRequestData(uuid=uuid)

        match link_type:
            case StorageItemType.file:
                response = await self._api.v3.file.link_status(data)
            case StorageItemType.folder:
                response = await self._api.v3.dir.link_status(data)
            case _:
                response = await self._api.v3.file.link_status(data)
                if response.data:
                    link_type = StorageItemType.file
                else:
                    response = await self._api.v3.dir.link_status(data)
                    link_type = StorageItemType.folder

        if not response.data or not response.data.exists:
            return PublicLinkStatus.not_exist()

        if link_type == StorageItemType.file:
            file_info = await self.file_info(uuid)
            key = file_info.metadata.key
            link_base_url = FILEN_PUBLIC_FILE_LINK_BASE_URL
        else:
            master_keys = await self._ensure_master_keys()
            key = await self._runner.run_sync(decrypt_metadata, response.data.key, master_keys)
            link_base_url = FILEN_PUBLIC_FOLDER_LINK_BASE_URL

        link_path = quote(f'{response.data.uuid}#{key}')
        link = f'{link_base_url}/{link_path}'

        return response.data_as(PublicLinkStatus, type=link_type, key=key, link=link)

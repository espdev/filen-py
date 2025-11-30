from typing import Final, Literal
from mimetypes import guess_type
import os
from urllib.parse import quote
from uuid import UUID, uuid4

from filen._context import Context
from filen.api.v3.models import StorageItemExistsRequestData, StorageItemUUIDRequestData
from filen.api.v3.models.dir import (
    BASE_PARENT,
    FolderContentRequestData,
    FolderContentType,
    FolderCreateRequestData,
    FolderMoveRequestData,
    FolderPublicLinkAddRequestData,
    FolderPublicLinkEditRequestData,
    FolderPublicLinkSizeRequestData,
    FolderRenameRequestData,
)
from filen.api.v3.models.file import FileMoveRequestData, FilePublicLinkEditRequestData, FileRenameRequestData
from filen.api.v3.models.link import PublicLinkExpiration
from filen.config import FILEN_PUBLIC_FILE_LINK_BASE_URL, FILEN_PUBLIC_FOLDER_LINK_BASE_URL, STORAGE_ROOT_NAME
from filen.crypto import (
    decrypt_metadata,
    decrypt_metadata_model,
    encrypt_metadata,
    encrypt_metadata_model,
    generate_metadata_encryption_key,
    hash_name,
    hash_public_link_password,
)
from filen.errors import StorageError

from ._base import AsyncRepoBase, RepoBase, repo
from ._lock import AsyncLock, Lock, LockResource
from .models import (
    CreateFolderInfo,
    FileInfo,
    FileMetadata,
    FolderContent,
    FolderInfo,
    FolderMetadata,
    FolderPublicLinkSize,
    PublicLinkStatus,
    StorageItemExists,
    StorageItemPresent,
    StorageItemType,
)

type ItemId = UUID | str

NAME_MAX_LEN: Final = 255


def _decrypt_folder_metadata(
    metadata: str,
    keys: str | list[str],
    auth_version,
    is_root: bool = False,
) -> tuple[FolderMetadata, str]:
    if is_root:
        metadata = FolderMetadata(name=STORAGE_ROOT_NAME)
        name_hashed = STORAGE_ROOT_NAME
    else:
        metadata = decrypt_metadata_model(FolderMetadata, metadata, keys)
        name_hashed = hash_name(metadata.name, auth_version)
    return metadata, name_hashed


def _decrypt_file_metadata(metadata: str, keys: str | list[str], auth_version) -> tuple[FileMetadata, str]:
    metadata = decrypt_metadata_model(FileMetadata, metadata, keys)
    name_hashed = hash_name(metadata.name, auth_version)
    return metadata, name_hashed


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

    @staticmethod
    def _normalize_uuid(uuid: ItemId) -> UUID:
        if isinstance(uuid, str):
            return UUID(uuid)
        else:
            return uuid

    @staticmethod
    def _collect_folder_content(files_info, folders_info, decryption_results, trash: bool = False) -> FolderContent:
        files = []
        folders = []

        for (t, i), (metadata, name_hashed) in sorted(decryption_results.items(), key=lambda item: item[0][1]):
            match t:
                case StorageItemType.file:
                    file_info = files_info[i].model_dump(exclude={'metadata'})
                    file_info['metadata'] = metadata
                    file_info['name_hashed'] = file_info.get('name_hashed', name_hashed)
                    file_info['trash'] = file_info.get('trash', trash)
                    files.append(FileInfo.model_validate(file_info))

                case StorageItemType.folder:
                    folder_info = folders_info[i].model_dump(exclude={'name'})
                    folder_info['name'] = metadata.name
                    folder_info['name_hashed'] = folder_info.get('name_hashed', name_hashed)
                    folder_info['trash'] = folder_info.get('trash', trash)
                    folders.append(FolderInfo.model_validate(folder_info))

        return FolderContent(
            files=files,
            folders=folders,
        )

    @staticmethod
    def _get_password_hash_and_salt(password: str | None) -> tuple[bool, str, str]:
        has_password = bool(password)
        password_hashed, salt = hash_public_link_password(password)
        return has_password, password_hashed, salt


class Storage(RepoBase, StorageMixIn):
    """Storage repository

    Provides methods for manipulating with directories and files in the cloud storage.
    """

    _drive_write_lock: Lock = repo(Lock, resource=LockResource.drive_write)

    def base_folder(self) -> UUID:
        """Retrieve the base foder UUID (root srorage UUID)"""

        return self._ensure_base_folder_uuid()

    def folder_info(self, uuid: ItemId | None = None) -> FolderInfo:
        """Retrieve folder info with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        uuid = self._normalize_uuid(uuid)

        folder_info = self._api.v3.dir.info(StorageItemUUIDRequestData(uuid=uuid)).data

        if uuid != self._context.base_folder_uuid:
            master_keys = self._ensure_master_keys()
            metadata, _ = _decrypt_folder_metadata(folder_info.name_encrypted, master_keys, self._context.auth_version)
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
                tg.add_task(
                    (StorageItemType.file, i),
                    _decrypt_file_metadata,
                    file.metadata,
                    master_keys,
                    self._context.auth_version,
                )

            for i, folder in enumerate(folder_content.folders):
                tg.add_task(
                    (StorageItemType.folder, i),
                    _decrypt_folder_metadata,
                    folder.name,
                    master_keys,
                    self._context.auth_version,
                )

        trash = uuid == FolderContentType.trash
        return self._collect_folder_content(folder_content.uploads, folder_content.folders, tg.results, trash=trash)

    def folder_download(self, uuid: ItemId | None = None) -> FolderContent:
        """Retrieve folder tree (flattened) with metadata decryption"""

        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        master_keys = self._ensure_master_keys()

        folder_download = self._api.v3.dir.download(StorageItemUUIDRequestData(uuid=uuid)).data

        with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task(
                    (StorageItemType.file, i),
                    _decrypt_file_metadata,
                    file.metadata,
                    master_keys,
                    self._context.auth_version,
                )

            for i, folder in enumerate(folder_download.folders):
                is_root = folder.uuid == self._context.base_folder_uuid
                tg.add_task(
                    (StorageItemType.folder, i),
                    _decrypt_folder_metadata,
                    folder.name,
                    master_keys,
                    self._context.auth_version,
                    is_root=is_root,
                )

        return self._collect_folder_content(folder_download.files, folder_download.folders, tg.results)

    def folder_present(self, uuid: ItemId) -> StorageItemPresent:
        """Checnk if a folder with given uuid exists"""

        response = self._api.v3.dir.present(StorageItemUUIDRequestData(uuid=uuid))
        if response.data.present:
            return response.data_as(StorageItemPresent, type=StorageItemType.folder)
        return StorageItemPresent.not_present()

    def folder_exists(self, name: str, parent: ItemId | None = None) -> StorageItemExists:
        """Check if a forlder with given name exists"""

        if parent is None:
            parent = self._ensure_base_folder_uuid()

        name_hashed = hash_name(name, self._context.auth_version)

        return self._api.v3.dir.exists(
            StorageItemExistsRequestData(
                parent=parent,
                name_hashed=name_hashed,
            ),
        ).data_as(StorageItemExists, type=StorageItemType.folder)

    def create_folder(self, name: str, parent: ItemId | None = None) -> CreateFolderInfo:
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

        with self._drive_write_lock:
            return self._api.v3.dir.create(data).data_as(CreateFolderInfo)

    def delete_folder(self, uuid: ItemId, permanent: bool = False) -> None:
        """Move folder to trash or delete permanently"""

        data = StorageItemUUIDRequestData(uuid=uuid)

        with self._drive_write_lock:
            if permanent:
                self._api.v3.dir.delete(data)
            else:
                self._api.v3.dir.trash(data)

    def move_folder(self, uuid: ItemId, to_uuid: ItemId, *, overwrite_existing: bool = False) -> None:
        """Move a folder to another folder"""

        # TODO: Add an option to merge the folder with an existing folder with the overwrite_existing option for files?

        uuid = self._normalize_uuid(uuid)
        to_uuid = self._normalize_uuid(to_uuid)

        if uuid == to_uuid:
            raise StorageError('The folder cannot be moved into itself.')

        if overwrite_existing:
            raise NotImplementedError('overwrite_existing option is not implemented for move_folder')

        data = FolderMoveRequestData(uuid=uuid, to=to_uuid)

        with self._drive_write_lock:
            self._api.v3.dir.move(data)

    def rename_folder(self, uuid: ItemId, new_name: str) -> None:
        """Rename a folder"""

        uuid = self._normalize_uuid(uuid)

        if uuid == self._ensure_base_folder_uuid():
            raise StorageError("Can't rename the root storage folder.")

        folder_info = self.folder_info(uuid)
        exists = self.folder_exists(new_name, folder_info.parent)
        if exists:
            if exists.uuid == uuid:
                return
            raise StorageError('A folder with the same name already exists in this folder.')

        key = self._ensure_master_key()
        metadata = FolderMetadata(name=new_name)

        metadata_enc = encrypt_metadata_model(metadata, key)
        name_hashed = hash_name(new_name, self._context.auth_version)

        data = FolderRenameRequestData(uuid=uuid, name=metadata_enc, name_hashed=name_hashed)

        with self._drive_write_lock:
            self._api.v3.dir.rename(data)

    def file_present(self, uuid: ItemId) -> StorageItemPresent:
        """Checnk if a file with given uuid exists"""

        response = self._api.v3.file.present(StorageItemUUIDRequestData(uuid=uuid))
        if response.data.present:
            return response.data_as(StorageItemPresent, type=StorageItemType.file)
        return StorageItemPresent.not_present()

    def file_exists(self, name: str, parent: ItemId | None = None) -> StorageItemExists:
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
        metadata, _ = _decrypt_file_metadata(file_info.metadata, master_keys, self._context.auth_version)

        return FileInfo(**file_info.model_dump(exclude={'metadata'}), metadata=metadata)

    def delete_file(self, uuid: ItemId, permanent: bool = False) -> None:
        """Move a file to trash or delete permanently"""

        data = StorageItemUUIDRequestData(uuid=uuid)

        with self._drive_write_lock:
            if permanent:
                self._api.v3.file.delete(data)
            else:
                self._api.v3.file.trash(data)

    def move_file(self, uuid: ItemId, to_uuid: ItemId, *, overwrite_existing: bool = False) -> None:
        """Move a file to another folder"""

        uuid = self._normalize_uuid(uuid)
        to_uuid = self._normalize_uuid(to_uuid)

        file_info = self.file_info(uuid)
        exists = self.file_exists(file_info.metadata.name, to_uuid)

        if exists:
            if overwrite_existing:
                self.delete_file(exists.uuid, permanent=False)
            else:
                raise StorageError('A file with the same name already exists in the destination folder.')

        data = FileMoveRequestData(uuid=uuid, to=to_uuid)

        with self._drive_write_lock:
            self._api.v3.file.move(data)

    def rename_file(self, uuid: ItemId, new_name: str, *, overwrite_existing: bool = False) -> None:
        uuid = self._normalize_uuid(uuid)

        file_info = self.file_info(uuid)
        exists = self.file_exists(new_name, file_info.parent)

        if exists:
            if exists.uuid == uuid:
                return
            if overwrite_existing:
                self.delete_file(exists.uuid, permanent=False)
            else:
                raise StorageError('A file with the same name already exists in this folder.')

        key = self._ensure_master_key()

        metadata = FileMetadata(
            **file_info.metadata.model_dump(exclude={'name', 'mime'}),
            name=new_name,
            mime=guess_type(new_name)[0] or file_info.metadata.mime,
        )

        name_hashed = hash_name(new_name, self._context.auth_version)
        name_enc = encrypt_metadata(new_name, metadata.key)
        metadata_enc = encrypt_metadata_model(metadata, key)

        data = FileRenameRequestData(uuid=uuid, metadata=metadata_enc, name=name_enc, name_hashed=name_hashed)

        with self._drive_write_lock:
            self._api.v3.file.rename(data)

    def empty_trash(self) -> None:
        """Empty the trash"""

        with self._drive_write_lock:
            self._api.v3.dir.empty_trash()

    def public_link_status(self, uuid: ItemId, link_type: StorageItemType | str | None = None) -> PublicLinkStatus:
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
            return PublicLinkStatus.not_exist(link_type=link_type, item_uuid=uuid)

        if link_type == StorageItemType.file:
            file_info = self.file_info(uuid)
            size = file_info.metadata.size
            key = file_info.metadata.key
            link_base_url = FILEN_PUBLIC_FILE_LINK_BASE_URL
        else:
            master_keys = self._ensure_master_keys()
            size = self.folder_public_link_size(uuid, response.data.uuid).size
            key = decrypt_metadata(response.data.key, master_keys)
            link_base_url = FILEN_PUBLIC_FOLDER_LINK_BASE_URL

        link_path = quote(f'{response.data.uuid}#{key}')
        link = f'{link_base_url}/{link_path}'

        return response.data_as(PublicLinkStatus, item_uuid=uuid, type=link_type, size=size, key=key, link=link)

    def folder_public_link_size(self, folder_uuid: ItemId, link_uuid: ItemId) -> FolderPublicLinkSize:
        """Return a folder public link size"""

        data = FolderPublicLinkSizeRequestData(uuid=folder_uuid, link_uuid=link_uuid)
        return self._api.v3.dir.link_size(data).data_as(FolderPublicLinkSize)

    def edit_file_public_link(
        self,
        link_uuid: ItemId,
        file_uuid: ItemId,
        action: Literal['enable', 'disable'] = 'enable',
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        has_password, password_hashed, salt = self._get_password_hash_and_salt(password)

        link_edit_data = FilePublicLinkEditRequestData(
            uuid=file_uuid,
            link_uuid=link_uuid,
            expiration=expiration,
            has_password=has_password,
            password_hashed=password_hashed,
            salt=salt,
            download_btn=download_btn,
            type=action,
        )
        self._api.v3.file.link_edit(link_edit_data)
        return self.public_link_status(file_uuid, StorageItemType.file)

    def edit_folder_public_link(
        self,
        folder_uuid: ItemId,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        has_password, password_hashed, salt = self._get_password_hash_and_salt(password)

        link_edit_data = FolderPublicLinkEditRequestData(
            uuid=folder_uuid,
            expiration=expiration,
            has_password=has_password,
            password_hashed=password_hashed,
            salt=salt,
            download_btn=download_btn,
        )
        self._api.v3.dir.link_edit(link_edit_data)
        return self.public_link_status(folder_uuid, StorageItemType.folder)

    def create_public_link(
        self,
        uuid: ItemId,
        link_type: StorageItemType,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        """Creates a public link for a file or folder"""

        uuid = self._normalize_uuid(uuid)

        if uuid == self._ensure_base_folder_uuid():
            raise StorageError('A public link cannot be created for the storage root folder.')

        link_uuid = uuid4()

        if link_type == StorageItemType.file:
            file_info = self.file_info(uuid)

            return self.edit_file_public_link(
                link_uuid=link_uuid,
                file_uuid=file_info.uuid,
                action='enable',
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )

        else:
            if self.public_link_status(uuid, link_type):
                self.remove_folder_public_link(uuid)

            folder_tree = self.folder_download(uuid)
            all_items = folder_tree.folders + folder_tree.files

            master_key = self._ensure_master_key()
            link_key = generate_metadata_encryption_key()
            link_key_enc = encrypt_metadata(link_key, master_key)

            with self._runner.task_group() as tg:
                for i, item in enumerate(all_items):
                    tg.add_task(
                        task_id=i,
                        func=self._add_item_to_directory_public_link,
                        item=item,
                        link_uuid=link_uuid,
                        key=link_key,
                        key_enc=link_key_enc,
                        expiration=expiration,
                    )

            return self.edit_folder_public_link(
                folder_uuid=uuid,
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )

    def remove_folder_public_link(self, item_uuid: ItemId) -> None:
        self._api.v3.dir.link_remove(StorageItemUUIDRequestData(uuid=item_uuid))

    def _add_item_to_directory_public_link(
        self,
        item: FileInfo | FolderInfo,
        link_uuid: UUID,
        key: str,
        key_enc: str,
        expiration: PublicLinkExpiration,
    ) -> None:
        if item.type == 'folder':
            metadata = FolderMetadata(name=item.name)
        else:
            metadata = item.metadata

        metadata_enc = encrypt_metadata_model(metadata, key)

        link_add_data = FolderPublicLinkAddRequestData(
            uuid=item.uuid,
            parent=item.parent or BASE_PARENT,
            link_uuid=link_uuid,
            type=item.type,
            metadata=metadata_enc,
            key=key_enc,
            expiration=expiration,
        )

        self._api.v3.dir.link_add(link_add_data)


class AsyncStorage(AsyncRepoBase, StorageMixIn):
    """Async Storage repository"""

    _drive_write_lock: AsyncLock = repo(AsyncLock, resource=LockResource.drive_write)

    async def base_folder(self) -> UUID:
        return await self._ensure_base_folder_uuid()

    async def folder_info(self, uuid: ItemId | None = None) -> FolderInfo:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        uuid = self._normalize_uuid(uuid)

        folder_info = (await self._api.v3.dir.info(StorageItemUUIDRequestData(uuid=uuid))).data

        if uuid != self._context.base_folder_uuid:
            master_keys = await self._ensure_master_keys()
            metadata, _ = await self._runner.run_sync(
                _decrypt_folder_metadata,
                folder_info.name_encrypted,
                master_keys,
                self._context.auth_version,
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
                tg.add_task(
                    (StorageItemType.file, i),
                    _decrypt_file_metadata,
                    file.metadata,
                    master_keys,
                    self._context.auth_version,
                )

            for i, folder in enumerate(folder_content.folders):
                tg.add_task(
                    (StorageItemType.folder, i),
                    _decrypt_folder_metadata,
                    folder.name,
                    master_keys,
                    self._context.auth_version,
                )

        trash = uuid == FolderContentType.trash
        return self._collect_folder_content(folder_content.uploads, folder_content.folders, tg.results, trash=trash)

    async def folder_download(self, uuid: ItemId | None = None) -> FolderContent:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        master_keys = await self._ensure_master_keys()

        folder_download = (await self._api.v3.dir.download(StorageItemUUIDRequestData(uuid=uuid))).data

        async with self._runner.task_group() as tg:
            for i, file in enumerate(folder_download.files):
                tg.add_task(
                    (StorageItemType.file, i),
                    _decrypt_file_metadata,
                    file.metadata,
                    master_keys,
                    self._context.auth_version,
                )

            for i, folder in enumerate(folder_download.folders):
                is_root = folder.uuid == self._context.base_folder_uuid
                tg.add_task(
                    (StorageItemType.folder, i),
                    _decrypt_folder_metadata,
                    folder.name,
                    master_keys,
                    self._context.auth_version,
                    is_root=is_root,
                )

        return self._collect_folder_content(folder_download.files, folder_download.folders, tg.results)

    async def folder_present(self, uuid: ItemId) -> StorageItemPresent:
        """Checnk if a folder with given uuid exists"""

        response = await self._api.v3.dir.present(StorageItemUUIDRequestData(uuid=uuid))
        if response.data.present:
            return response.data_as(StorageItemPresent, type=StorageItemType.folder)
        return StorageItemPresent.not_present()

    async def folder_exists(self, name: str, parent: ItemId | None = None) -> StorageItemExists:
        if parent is None:
            parent = await self._ensure_base_folder_uuid()

        name_hashed = await self._runner.run_sync(hash_name, name, self._context.auth_version)

        return (
            await self._api.v3.dir.exists(
                StorageItemExistsRequestData(parent=parent, name_hashed=name_hashed),
            )
        ).data_as(StorageItemExists, type=StorageItemType.folder)

    async def create_folder(self, name: str, parent: ItemId | None = None) -> CreateFolderInfo:
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

        async with self._drive_write_lock:
            return (await self._api.v3.dir.create(data)).data_as(CreateFolderInfo)

    async def delete_folder(self, uuid: ItemId, permanent: bool = False) -> None:
        """Move folder to trash or delete permanently"""

        data = StorageItemUUIDRequestData(uuid=uuid)

        async with self._drive_write_lock:
            if permanent:
                await self._api.v3.dir.delete(data)
            else:
                await self._api.v3.dir.trash(data)

    async def move_folder(self, uuid: ItemId, to_uuid: ItemId, overwrite_existing: bool = False) -> None:
        """Move a folder to another folder"""

        uuid = self._normalize_uuid(uuid)
        to_uuid = self._normalize_uuid(to_uuid)

        if uuid == to_uuid:
            raise StorageError('The folder cannot be moved into itself.')

        if overwrite_existing:
            raise NotImplementedError('overwrite_existing option is not implemented for move_folder')

        data = FolderMoveRequestData(uuid=uuid, to=to_uuid)

        async with self._drive_write_lock:
            await self._api.v3.dir.move(data)

    async def rename_folder(self, uuid: ItemId, new_name: str) -> None:
        uuid = self._normalize_uuid(uuid)

        if uuid == (await self._ensure_base_folder_uuid()):
            raise StorageError("Can't rename the root storage folder.")

        folder_info = await self.folder_info(uuid)
        exists = await self.folder_exists(new_name, folder_info.parent)
        if exists:
            if exists.uuid == uuid:
                return
            raise StorageError('A folder with the same name already exists in this folder.')

        key = await self._ensure_master_key()
        metadata = FolderMetadata(name=new_name)

        metadata_enc = await self._runner.run_sync(encrypt_metadata_model, metadata, key)
        name_hashed = await self._runner.run_sync(hash_name, new_name, self._context.auth_version)

        data = FolderRenameRequestData(uuid=uuid, name=metadata_enc, name_hashed=name_hashed)

        async with self._drive_write_lock:
            await self._api.v3.dir.rename(data)

    async def file_present(self, uuid: ItemId) -> StorageItemPresent:
        """Checnk if a file with given uuid exists"""

        response = await self._api.v3.file.present(StorageItemUUIDRequestData(uuid=uuid))
        if response.data.present:
            return response.data_as(StorageItemPresent, type=StorageItemType.file)
        return StorageItemPresent.not_present()

    async def file_exists(self, name: str, parent: ItemId | None = None) -> StorageItemExists:
        if parent is None:
            parent = await self._ensure_base_folder_uuid()

        name_hashed = await self._runner.run_sync(hash_name, name, self._context.auth_version)

        return (
            await self._api.v3.file.exists(
                StorageItemExistsRequestData(parent=parent, name_hashed=name_hashed),
            )
        ).data_as(StorageItemExists, type=StorageItemType.file)

    async def file_info(self, uuid: ItemId) -> FileInfo:
        master_keys = await self._ensure_master_keys()

        file_info = (await self._api.v3.file.info(StorageItemUUIDRequestData(uuid=uuid))).data
        metadata, _ = await self._runner.run_sync(
            _decrypt_file_metadata,
            file_info.metadata,
            master_keys,
            self._context.auth_version,
        )

        return FileInfo(**file_info.model_dump(exclude={'metadata'}), metadata=metadata)

    async def delete_file(self, uuid: ItemId, permanent: bool = False) -> None:
        """Move a file to trash or delete permanently"""

        data = StorageItemUUIDRequestData(uuid=uuid)

        async with self._drive_write_lock:
            if permanent:
                await self._api.v3.file.delete(data)
            else:
                await self._api.v3.file.trash(data)

    async def move_file(self, uuid: ItemId, to_uuid: ItemId, *, overwrite_existing: bool = False) -> None:
        """Move a file to another folder"""

        uuid = self._normalize_uuid(uuid)
        to_uuid = self._normalize_uuid(to_uuid)

        file_info = await self.file_info(uuid)
        exists = await self.file_exists(file_info.metadata.name, to_uuid)

        if exists:
            if overwrite_existing:
                await self.delete_file(exists.uuid, permanent=False)
            else:
                raise StorageError('A file with the same name already exists in the destination folder.')

        data = FileMoveRequestData(uuid=uuid, to=to_uuid)

        async with self._drive_write_lock:
            await self._api.v3.file.move(data)

    async def rename_file(self, uuid: ItemId, new_name: str, *, overwrite_existing: bool = False) -> None:
        """Rename a file"""

        uuid = self._normalize_uuid(uuid)

        file_info = await self.file_info(uuid)
        exists = await self.file_exists(new_name, file_info.parent)

        if exists:
            if exists.uuid == uuid:
                return
            if overwrite_existing:
                await self.delete_file(exists.uuid, permanent=False)
            else:
                raise StorageError('A file with the same name already exists in this folder.')

        key = await self._ensure_master_key()

        metadata = FileMetadata(
            **file_info.metadata.model_dump(exclude={'name', 'mime'}),
            name=new_name,
            mime=guess_type(new_name)[0] or file_info.metadata.mime,
        )

        name_hashed = await self._runner.run_sync(hash_name, new_name, self._context.auth_version)
        name_enc = await self._runner.run_sync(encrypt_metadata, new_name, metadata.key)
        metadata_enc = await self._runner.run_sync(encrypt_metadata_model, metadata, key)

        data = FileRenameRequestData(uuid=uuid, metadata=metadata_enc, name=name_enc, name_hashed=name_hashed)

        async with self._drive_write_lock:
            await self._api.v3.file.rename(data)

    async def empty_trash(self) -> None:
        """Empty the trash"""

        async with self._drive_write_lock:
            await self._api.v3.dir.empty_trash()

    async def public_link_status(
        self,
        uuid: ItemId,
        link_type: StorageItemType | str | None = None,
    ) -> PublicLinkStatus:
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
            return PublicLinkStatus.not_exist(link_type=link_type, item_uuid=uuid)

        if link_type == StorageItemType.file:
            file_info = await self.file_info(uuid)
            size = file_info.metadata.size
            key = file_info.metadata.key
            link_base_url = FILEN_PUBLIC_FILE_LINK_BASE_URL
        else:
            master_keys = await self._ensure_master_keys()
            size = (await self.folder_public_link_size(uuid, response.data.uuid)).size
            key = await self._runner.run_sync(decrypt_metadata, response.data.key, master_keys)
            link_base_url = FILEN_PUBLIC_FOLDER_LINK_BASE_URL

        link_path = quote(f'{response.data.uuid}#{key}')
        link = f'{link_base_url}/{link_path}'

        return response.data_as(PublicLinkStatus, item_uuid=uuid, type=link_type, size=size, key=key, link=link)

    async def folder_public_link_size(self, folder_uuid: ItemId, link_uuid: ItemId) -> FolderPublicLinkSize:
        """Return a folder public link size"""

        data = FolderPublicLinkSizeRequestData(uuid=folder_uuid, link_uuid=link_uuid)
        return (await self._api.v3.dir.link_size(data)).data_as(FolderPublicLinkSize)

    async def edit_file_public_link(
        self,
        link_uuid: ItemId,
        file_uuid: ItemId,
        action: Literal['enable', 'disable'] = 'enable',
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        has_password, password_hashed, salt = self._get_password_hash_and_salt(password)

        link_edit_data = FilePublicLinkEditRequestData(
            uuid=file_uuid,
            link_uuid=link_uuid,
            expiration=expiration,
            has_password=has_password,
            password_hashed=password_hashed,
            salt=salt,
            download_btn=download_btn,
            type=action,
        )

        await self._api.v3.file.link_edit(link_edit_data)
        return await self.public_link_status(file_uuid, StorageItemType.file)

    async def edit_folder_public_link(
        self,
        folder_uuid: ItemId,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        has_password, password_hashed, salt = self._get_password_hash_and_salt(password)

        link_edit_data = FolderPublicLinkEditRequestData(
            uuid=folder_uuid,
            expiration=expiration,
            has_password=has_password,
            password_hashed=password_hashed,
            salt=salt,
            download_btn=download_btn,
        )

        await self._api.v3.dir.link_edit(link_edit_data)
        return await self.public_link_status(folder_uuid, StorageItemType.folder)

    async def create_public_link(
        self,
        uuid: ItemId,
        link_type: StorageItemType,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        """Creates a public link for a file or folder"""

        uuid = self._normalize_uuid(uuid)

        if uuid == (await self._ensure_base_folder_uuid()):
            raise StorageError('A public link cannot be created for the storage root folder.')

        link_uuid = uuid4()

        if link_type == StorageItemType.file:
            file_info = await self.file_info(uuid)

            return await self.edit_file_public_link(
                link_uuid=link_uuid,
                action='enable',
                file_uuid=file_info.uuid,
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )

        else:
            if await self.public_link_status(uuid, link_type):
                await self.remove_folder_public_link(uuid)

            folder_tree = await self.folder_download(uuid)
            all_items = folder_tree.folders + folder_tree.files

            master_key = await self._ensure_master_key()
            link_key = generate_metadata_encryption_key()
            link_key_enc = await self._runner.run_sync(encrypt_metadata, link_key, master_key)

            async with self._runner.task_group() as tg:
                for i, item in enumerate(all_items):
                    tg.add_task(
                        task_id=i,
                        func=self._add_item_to_directory_public_link,
                        item=item,
                        link_uuid=link_uuid,
                        key=link_key,
                        key_enc=link_key_enc,
                        expiration=expiration,
                    )

            return await self.edit_folder_public_link(
                folder_uuid=uuid,
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )

    async def remove_folder_public_link(self, item_uuid: ItemId) -> None:
        await self._api.v3.dir.link_remove(StorageItemUUIDRequestData(uuid=item_uuid))

    async def _add_item_to_directory_public_link(
        self,
        item: FileInfo | FolderInfo,
        link_uuid: UUID,
        key: str,
        key_enc: str,
        expiration: PublicLinkExpiration,
    ) -> None:
        if item.type == 'folder':
            metadata = FolderMetadata(name=item.name)
        else:
            metadata = item.metadata

        metadata_enc = await self._runner.run_sync(encrypt_metadata_model, metadata, key)

        link_add_data = FolderPublicLinkAddRequestData(
            uuid=item.uuid,
            parent=item.parent or BASE_PARENT,
            link_uuid=link_uuid,
            type=item.type,
            metadata=metadata_enc,
            key=key_enc,
            expiration=expiration,
        )

        await self._api.v3.dir.link_add(link_add_data)

from typing import Final
import re
from uuid import UUID

from filen._logging import logger
from filen.errors import StorageError

from ._base import AsyncRepoBase, RepoBase, repo
from ._storage import AsyncStorage, Storage
from .models import (
    FileDetail,
    FolderContent,
    FolderDetail,
    PublicLinkExpiration,
    PublicLinkStatus,
    StorageItemExists,
    StorageItemType,
    StorageItemTypeLiteral,
)

TRASH_PATH: Final = '/<trash>'


class FSMixIn:
    _storage: Storage | AsyncStorage
    re_path_multi_sep = re.compile(r'/{2,}')

    @classmethod
    def _normalize_path(cls, path: str) -> str:
        src_path = path
        path = path.strip().strip('/').strip('\\').replace('\\', '/')
        path = cls.re_path_multi_sep.sub('/', path)
        path = f'/{path}'
        if path != src_path:
            logger.debug('Normalize path %r -> %r', src_path, path)
        return path

    def _path_parts(self, path: str) -> list[str]:
        names = path.lstrip('/').split('/')
        [self._storage.check_name(name) for name in names]
        return names

    @staticmethod
    def _check_path(path: str, status: StorageItemExists, raise_for_file: bool = False):
        if not status:
            raise StorageError('%r does not exist.', path)
        elif raise_for_file and status.type != StorageItemType.folder:
            raise StorageError('%r is not a directory.', path)

    @staticmethod
    def _collect_folder_content(
        path: str,
        folder_content: FolderContent,
        detail: bool,
    ) -> list[str | FileDetail | FolderDetail]:
        content = []
        path = path.rstrip('/')

        for folder_info in folder_content.folders:
            if detail:
                item = FolderDetail.from_info(path, folder_info)
            else:
                item = f'{path}/{folder_info.name}'
            content.append(item)

        for file_info in folder_content.files:
            if detail:
                item = FileDetail.from_info(path, file_info)
            else:
                item = f'{path}/{file_info.metadata.name}'
            content.append(item)

        return content

    @staticmethod
    def _collect_items_in_trash(
        folder_content: FolderContent, item_type: StorageItemType | StorageItemTypeLiteral | None
    ) -> list[FolderDetail | FileDetail]:
        match item_type:
            case StorageItemType.folder:
                return [FolderDetail.from_info(TRASH_PATH, f) for f in folder_content.folders]
            case StorageItemType.file:
                return [FileDetail.from_info(TRASH_PATH, f) for f in folder_content.files]
            case _:
                folders = [FolderDetail.from_info(TRASH_PATH, f) for f in folder_content.folders]
                files = [FileDetail.from_info(TRASH_PATH, f) for f in folder_content.files]
                return folders + files


class FS(RepoBase, FSMixIn):
    """High-level filesystem-like repository to manipulate files and folders"""

    _storage: Storage = repo(Storage)

    def exists(self, path: str) -> StorageItemExists:
        """Check is a path exists"""

        path = self._normalize_path(path)
        base_uuid = self._ensure_base_folder_uuid()

        if path == '/':
            return StorageItemExists.folder_exists(base_uuid)

        try:
            parts = self._path_parts(path)
        except StorageError:
            return StorageItemExists.not_exist()

        parent = base_uuid

        for name in parts[:-1]:
            folder_exists = self._storage.folder_exists(name, parent)
            if not folder_exists.exists:
                return folder_exists
            parent = folder_exists.uuid

        folder_exists = self._storage.folder_exists(parts[-1], parent)
        if folder_exists.exists:
            return folder_exists
        return self._storage.file_exists(parts[-1], parent)

    def ls(self, path: str, detail: bool = False) -> list[str | FileDetail | FolderDetail]:
        """List files and folders at path"""

        if path in (TRASH_PATH, TRASH_PATH.strip('/')):
            return self.trash()

        path = self._normalize_path(path)

        if path == '/':
            folder_content = self._storage.folder_content()
            return self._collect_folder_content(path, folder_content, detail=detail)

        item_exists = self.exists(path)

        if not item_exists.exists:
            raise StorageError(f'No such file or directory {path!r}')

        if item_exists.type == StorageItemType.file:
            if detail:
                file_info = self._storage.file_info(item_exists.uuid)
                return [FileDetail.from_info(path, file_info)]
            else:
                return [self._path_parts(path)[-1]]
        else:
            folder_content = self._storage.folder_content(item_exists.uuid)
            return self._collect_folder_content(path, folder_content, detail=detail)

    def trash(
        self,
        item_type: StorageItemType | StorageItemTypeLiteral | None = None,
    ) -> list[FolderDetail | FileDetail]:
        """Return the list of folders and/or files in trash"""

        folder_content = self._storage.folder_content('trash')
        return self._collect_items_in_trash(folder_content, item_type)

    def mkdir(self, path: str) -> UUID:
        """Create a directory on the cloud storage with parents for given path

        Returns item UUID for created folder.
        """

        parent_uuid = self._ensure_base_folder_uuid()
        path = self._normalize_path(path)

        if path == '/':
            return parent_uuid

        for name in self._path_parts(path):
            folder_created = self._storage.create_folder(name, parent_uuid)
            parent_uuid = folder_created.uuid

        return parent_uuid

    def mv(
        self,
        src_path: str,
        dst_path: str,
        *,
        ensure_folder: bool = True,
        overwrite_existing: bool = False,
    ) -> None:
        """Move a file or folder to the destination folder"""

        src_status = self.exists(src_path)
        dst_status = self.exists(dst_path)

        if not dst_status.exists and ensure_folder:
            uuid = self.mkdir(dst_path)
            dst_status = StorageItemExists.folder_exists(uuid)

        self._check_path(src_path, src_status)
        self._check_path(dst_path, dst_status, raise_for_file=True)

        if src_status.type == StorageItemType.file:
            self._storage.move_file(src_status.uuid, dst_status.uuid, overwrite_existing=overwrite_existing)
        else:
            self._storage.move_folder(src_status.uuid, dst_status.uuid, overwrite_existing=overwrite_existing)

    def rm(self, path: str, permanent: bool = False) -> None:
        """Delete a file or folder"""

        exists = self.exists(path)
        self._check_path(path, exists)

        if exists.type == StorageItemType.file:
            self._storage.delete_file(exists.uuid, permanent=permanent)
        else:
            self._storage.delete_folder(exists.uuid, permanent=permanent)

    def rename(self, path: str, new_name: str, *, overwrite_existing_file: bool = False) -> None:
        """Rename a file or folder"""

        exists = self.exists(path)
        self._check_path(path, exists)

        if exists.type == StorageItemType.file:
            self._storage.rename_file(exists.uuid, new_name, overwrite_existing=overwrite_existing_file)
        else:
            self._storage.rename_folder(exists.uuid, new_name)

    def link(self, path: str, detail: bool = False) -> str | PublicLinkStatus | None:
        """Get a public link status for the file/folder"""

        exists = self.exists(path)
        if not exists:
            return PublicLinkStatus.not_exist() if detail else None

        link_status = self._storage.public_link_status(exists.uuid, exists.type)
        return link_status if detail else link_status.link

    def mklink(
        self,
        path: str,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        """Creates a public link for a file or folder path

        If the link is already exist, it will be re-created.
        """

        exists = self.exists(path)
        if not exists:
            raise StorageError(f'No such file or directory {path!r}')

        return self._storage.create_public_link(
            uuid=exists.uuid,
            link_type=exists.type,
            expiration=expiration,
            password=password,
            download_btn=download_btn,
        )

    def chlink(
        self,
        path: str,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        """Edit a public link for a file or folder path"""

        link_status = self.link(path, detail=True)

        if not link_status:
            raise StorageError(f'There is no public link for {path!r}')

        if link_status.type == StorageItemType.file:
            return self._storage.edit_file_public_link(
                link_uuid=link_status.uuid,
                file_uuid=link_status.item_uuid,
                action='enable',
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )
        else:
            return self._storage.edit_folder_public_link(
                folder_uuid=link_status.item_uuid,
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )

    def rmlink(self, path: str) -> None:
        """Remove a public link for a file or folder path"""

        link_status = self.link(path, detail=True)

        if not link_status:
            raise StorageError(f'There is no public link for {path!r}')

        if link_status.type == StorageItemType.folder:
            self._storage.remove_folder_public_link(link_status.item_uuid)
        else:
            self._storage.edit_file_public_link(
                link_uuid=link_status.uuid,
                file_uuid=link_status.item_uuid,
                action='disable',
            )


class AsyncFS(AsyncRepoBase, FSMixIn):
    """Async High-level filesystem-like repository to manipulate files and folders"""

    _storage: AsyncStorage = repo(AsyncStorage)

    async def exists(self, path: str) -> StorageItemExists:
        """Check is a path exists"""

        path = self._normalize_path(path)
        base_uuid = await self._ensure_base_folder_uuid()

        if path == '/':
            return StorageItemExists.folder_exists(base_uuid)

        try:
            parts = self._path_parts(path)
        except StorageError:
            return StorageItemExists.not_exist()

        parent = base_uuid

        for name in parts[:-1]:
            folder_exists = await self._storage.folder_exists(name, parent)
            if not folder_exists.exists:
                return folder_exists
            parent = folder_exists.uuid

        folder_exists = await self._storage.folder_exists(parts[-1], parent)
        if folder_exists.exists:
            return folder_exists
        return await self._storage.file_exists(parts[-1], parent)

    async def ls(self, path: str, detail: bool = False) -> list[str | FileDetail | FolderDetail]:
        """List files and folders at path"""

        if path in (TRASH_PATH, TRASH_PATH.strip('/')):
            return await self.trash()

        path = self._normalize_path(path)

        if path == '/':
            folder_content = await self._storage.folder_content()
            return self._collect_folder_content(path, folder_content, detail=detail)

        item_exists = await self.exists(path)

        if not item_exists.exists:
            raise StorageError(f'No such file or directory {path!r}')

        if item_exists.type == StorageItemType.file:
            if detail:
                file_info = await self._storage.file_info(item_exists.uuid)
                return [FileDetail.from_info(path, file_info)]
            else:
                return [self._path_parts(path)[-1]]
        else:
            folder_content = await self._storage.folder_content(item_exists.uuid)
            return self._collect_folder_content(path, folder_content, detail=detail)

    async def trash(
        self,
        item_type: StorageItemType | StorageItemTypeLiteral | None = None,
    ) -> list[FolderDetail | FileDetail]:
        """Return the list of folders and/or files in trash"""

        folder_content = await self._storage.folder_content('trash')
        return self._collect_items_in_trash(folder_content, item_type)

    async def mkdir(self, path: str) -> UUID:
        """Create a directory on the cloud storage with parents for given path"""

        parent_uuid = await self._ensure_base_folder_uuid()
        path = self._normalize_path(path)

        if path == '/':
            return parent_uuid

        for name in self._path_parts(path):
            folder_created = await self._storage.create_folder(name, parent_uuid)
            parent_uuid = folder_created.uuid

        return parent_uuid

    async def mv(
        self,
        src_path: str,
        dst_path: str,
        *,
        ensure_folder: bool = True,
        overwrite_existing: bool = False,
    ) -> None:
        """Move a file or folder to the destination folder"""

        src_status = await self.exists(src_path)
        dst_status = await self.exists(dst_path)

        if not dst_status.exists and ensure_folder:
            uuid = await self.mkdir(dst_path)
            dst_status = StorageItemExists.folder_exists(uuid)

        self._check_path(src_path, src_status)
        self._check_path(dst_path, dst_status, raise_for_file=True)

        if src_status.type == StorageItemType.file:
            await self._storage.move_file(src_status.uuid, dst_status.uuid, overwrite_existing=overwrite_existing)
        else:
            await self._storage.move_folder(src_status.uuid, dst_status.uuid, overwrite_existing=overwrite_existing)

    async def rm(self, path: str, permanent: bool = False) -> None:
        """Delete a file or folder"""

        exists = await self.exists(path)
        self._check_path(path, exists)

        if exists.type == StorageItemType.file:
            await self._storage.delete_file(exists.uuid, permanent=permanent)
        else:
            await self._storage.delete_folder(exists.uuid, permanent=permanent)

    async def rename(self, path: str, new_name: str, *, overwrite_existing_file: bool = False) -> None:
        """Rename a file or folder"""

        exists = await self.exists(path)
        self._check_path(path, exists)

        if exists.type == StorageItemType.file:
            await self._storage.rename_file(exists.uuid, new_name, overwrite_existing=overwrite_existing_file)
        else:
            await self._storage.rename_folder(exists.uuid, new_name)

    async def link(self, path: str, detail: bool = False) -> str | PublicLinkStatus | None:
        """Get a public link status for the file/folder"""

        exists = await self.exists(path)
        if not exists:
            return PublicLinkStatus.not_exist() if detail else None

        link_status = await self._storage.public_link_status(exists.uuid, exists.type)
        return link_status if detail else link_status.link

    async def mklink(
        self,
        path: str,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        """Creates a public link for a file or folder path

        If the link is already exist, it will be re-created.
        """

        exists = await self.exists(path)
        if not exists:
            raise StorageError(f'No such file or directory {path!r}')

        return await self._storage.create_public_link(
            uuid=exists.uuid,
            link_type=exists.type,
            expiration=expiration,
            password=password,
            download_btn=download_btn,
        )

    async def chlink(
        self,
        path: str,
        expiration: PublicLinkExpiration = 'never',
        password: str | None = None,
        download_btn: bool = True,
    ) -> PublicLinkStatus:
        """Edit a public link for a file or folder path"""

        link_status = await self.link(path, detail=True)

        if not link_status:
            raise StorageError(f'There is no public link for {path!r}')

        if link_status.type == StorageItemType.file:
            return await self._storage.edit_file_public_link(
                link_uuid=link_status.uuid,
                file_uuid=link_status.item_uuid,
                action='enable',
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )
        else:
            return await self._storage.edit_folder_public_link(
                folder_uuid=link_status.item_uuid,
                expiration=expiration,
                password=password,
                download_btn=download_btn,
            )

    async def rmlink(self, path: str) -> None:
        """Remove a public link for a file or folder path"""

        link_status = await self.link(path, detail=True)

        if not link_status:
            raise StorageError(f'There is no public link for {path!r}')

        if link_status.type == StorageItemType.folder:
            await self._storage.remove_folder_public_link(link_status.item_uuid)
        else:
            await self._storage.edit_file_public_link(
                link_uuid=link_status.uuid,
                file_uuid=link_status.item_uuid,
                action='disable',
            )

from typing import Final
from os import PathLike
from pathlib import Path
import re
from uuid import UUID

from anyio import open_file
from humanize import naturalsize

from filen._logging import logger
from filen.crypto import hash_file
from filen.errors import DownloadError, StorageError

from ._base import AsyncRepoBase, RepoBase, repo
from ._download import AsyncDownloadStatusCallback
from ._storage import AsyncStorage, Storage
from .models import (
    FileDetail,
    FileInfo,
    FolderContent,
    FolderDetail,
    FolderSizeInfo,
    FolderTreeItem,
    PublicLinkExpiration,
    PublicLinkStatus,
    StorageItemExists,
    StorageItemType,
    StorageItemTypeLiteral,
)

TRASH_PATH: Final = '<trash>'
READ_CHUNK: Final = 4 * 1024 * 1024

type Tree = list[FolderTreeItem]
type LocalPath = str | Path | PathLike


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

    @staticmethod
    def _walk_folder_tree(path: str, uuid: UUID, content: FolderContent, detail: bool, internal: bool = False) -> Tree:
        """Make a folder tree from flattened downloaded folder content in os.walk format"""

        tree_map = {uuid: [[], []]}
        path_map = {uuid: path}

        for folder in content.folders:
            if folder.uuid == uuid:
                # root folder, do not include to tree map
                continue

            folder_path = f'{path_map[folder.parent]}/{folder.name}'

            if detail:
                if internal:
                    folder_info = folder
                else:
                    folder_info = FolderDetail.from_info(folder_path, folder)
            else:
                folder_info = folder.name

            tree_map[folder.parent][0].append(folder_info)

            if folder.uuid not in tree_map:
                path_map[folder.uuid] = folder_path
                tree_map[folder.uuid] = [[], []]

        for file in content.files:
            if detail:
                file_path = f'{path_map[file.parent]}/{file.metadata.name}'
                if internal:
                    file_info = file
                else:
                    file_info = FileDetail.from_info(file_path, file)
            else:
                file_info = file.metadata.name
            tree_map[file.parent][1].append(file_info)

        tree: Tree = []

        for parent, (folders, files) in tree_map.items():
            if detail:
                folders.sort(key=lambda info: info.name)
                if internal:
                    files.sort(key=lambda info: info.metadata.name)
                else:
                    files.sort(key=lambda info: info.name)
            else:
                folders.sort()
                files.sort()

            tree.append(FolderTreeItem(path_map[parent], folders, files))

        tree.sort(key=lambda item: item.path)
        return tree


class FS(RepoBase, FSMixIn):
    """High-level filesystem-like repository to manipulate files and folders in the storage"""

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

        if path.strip('/') == TRASH_PATH:
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

    def tree(self, path: str, detail: bool = False) -> Tree:
        """List folders and files at path recursive in os.walk format"""

        exists = self.exists(path)
        self._check_path(path, exists, raise_for_file=True)
        folder_content = self._storage.folder_download(exists.uuid)

        # make folder tree in os.walk format
        return self._walk_folder_tree(path, exists.uuid, folder_content, detail)

    def trash(
        self,
        item_type: StorageItemType | StorageItemTypeLiteral | None = None,
    ) -> list[FolderDetail | FileDetail]:
        """Return the list of folders and/or files in trash"""

        folder_content = self._storage.folder_content('trash')
        return self._collect_items_in_trash(folder_content, item_type)

    def empty_trash(self) -> None:
        """Empty the trash"""

        self._storage.empty_trash()

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

    def dirsize(self, path: str, *, trash: bool = False) -> FolderSizeInfo:
        """Return a folder size info"""

        exists = self.exists(path)
        self._check_path(path, exists, raise_for_file=True)
        return self._storage.folder_size(exists.uuid, trash=trash)

    def move(
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

    def remove(self, path: str, *, permanent: bool = False) -> None:
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
    """Async high-level filesystem-like repository to manipulate files and folders in the storage"""

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

        if path.strip('/') == TRASH_PATH:
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

    async def tree(self, path: str, detail: bool = False) -> Tree:
        """List folders and files at path recursive in os.walk format"""

        exists = await self.exists(path)
        self._check_path(path, exists, raise_for_file=True)
        folder_content = await self._storage.folder_download(exists.uuid)

        # make folder tree in os.walk format
        return self._walk_folder_tree(path, exists.uuid, folder_content, detail)

    async def trash(
        self,
        item_type: StorageItemType | StorageItemTypeLiteral | None = None,
    ) -> list[FolderDetail | FileDetail]:
        """Return the list of folders and/or files in trash"""

        folder_content = await self._storage.folder_content('trash')
        return self._collect_items_in_trash(folder_content, item_type)

    async def empty_trash(self) -> None:
        """Empty the trash"""

        await self._storage.empty_trash()

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

    async def dirsize(self, path: str, *, trash: bool = False) -> FolderSizeInfo:
        """Return a folder size info"""

        exists = await self.exists(path)
        self._check_path(path, exists, raise_for_file=True)
        return await self._storage.folder_size(exists.uuid, trash=trash)

    async def move(
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

    async def remove(self, path: str, *, permanent: bool = False) -> None:
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

    async def download(
        self,
        src_path: str,
        dst_path: LocalPath,
        *,
        ensure_folder: bool = True,
        resume_download: bool = False,
        verify_hash: bool = False,
        status_callback: AsyncDownloadStatusCallback | None = None,
    ) -> None:
        """Download a file or folder from the storage to local folder"""

        exists = await self.exists(src_path)
        self._check_path(src_path, exists)

        dst_path = Path(dst_path).expanduser().absolute()
        if not dst_path.is_dir():
            if ensure_folder:
                dst_path.mkdir(parents=True)
            else:
                raise OSError(f'Destination folder {dst_path} does not exist.')

        match exists.type:
            case StorageItemType.file:
                file_info = await self._storage.file_info(exists.uuid)
                local_file_path = dst_path / file_info.metadata.name
                await self._download_file(
                    file_info,
                    local_file_path,
                    resume_download=resume_download,
                    verify_hash=verify_hash,
                    status_callback=status_callback,
                )
                logger.debug("File %r downloaded to '%s'", src_path, local_file_path)

            case StorageItemType.folder:
                # folder_content = await self._storage.folder_download(exists.uuid)
                # tree = self._walk_folder_tree(src_path, exists.uuid, folder_content, detail=True, internal=True)
                raise NotImplementedError

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

    async def _download_file(
        self,
        file_info: FileInfo,
        local_file_path: Path,
        *,
        resume_download: bool = False,
        verify_hash: bool = False,
        status_callback: AsyncDownloadStatusCallback | None = None,
    ) -> None:
        if verify_hash and not file_info.metadata.hash:
            raise DownloadError(
                "Can't verify the file hash. FileInfo does not contain information about the file hash!"
            )

        local_file_path_tmp = local_file_path.with_suffix(f'{local_file_path.suffix}.part')

        if resume_download and local_file_path_tmp.exists():
            stat = local_file_path_tmp.stat()
            start = stat.st_size
            if start > file_info.metadata.size:
                mode = 'wb'
                start = None
                logger.debug("The file %r has been changed, can't resume downloading.", file_info.metadata.name)
            else:
                mode = 'ab'
                logger.debug(
                    "Resuming file %r download to '%s' from %s",
                    file_info.metadata.name,
                    local_file_path,
                    naturalsize(stat.st_size, binary=True),
                )
        else:
            mode = 'wb'
            start = None

        try:
            if start is None or start < file_info.metadata.size:
                async with await open_file(local_file_path_tmp, mode) as fp:
                    async for chunk in self._storage.download.stream(
                        file_info,
                        start=start,
                        status_callback=status_callback,
                    ):
                        await fp.write(chunk)
        except Exception:
            if not resume_download:
                local_file_path_tmp.unlink(missing_ok=True)
            raise

        if verify_hash:
            file_hash = await self._runner.run_sync(hash_file, local_file_path_tmp)
            if file_hash != file_info.metadata.hash:
                local_file_path_tmp.unlink(missing_ok=True)
                raise DownloadError(f"The file hash verification failed for downloaded file '{local_file_path}'.")

        local_file_path.unlink(missing_ok=True)
        local_file_path_tmp.rename(local_file_path)

import re
from uuid import UUID

from filen._logging import logger
from filen.errors import StorageError

from ._base import AsyncRepoBase, RepoBase, repo
from ._storage import AsyncStorage, Storage
from .models import FileDetail, FolderContent, FolderDetail, StorageItemExists, StorageItemType


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


class AsyncFS(AsyncRepoBase, FSMixIn):
    """Async High-level filesystem-like repository to manipulate files and folders"""

    _storage: AsyncStorage = repo(AsyncStorage)

    async def exists(self, path: str) -> StorageItemExists:
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

    async def mkdir(self, path: str) -> UUID:
        parent_uuid = await self._ensure_base_folder_uuid()
        path = self._normalize_path(path)

        if path == '/':
            return parent_uuid

        for name in self._path_parts(path):
            folder_created = await self._storage.create_folder(name, parent_uuid)
            parent_uuid = folder_created.uuid

        return parent_uuid

import re
from uuid import UUID

from filen._log import logger

from ._base import AsyncRepoBase, RepoBase, repo
from ._storage import AsyncStorage, Storage


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


class FS(RepoBase, FSMixIn):
    """High-level filesystem-like repository to manipulate files and folders"""

    _storage: Storage = repo(Storage)

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

    async def mkdir(self, path: str) -> UUID:
        parent_uuid = await self._ensure_base_folder_uuid()
        path = self._normalize_path(path)

        if path == '/':
            return parent_uuid

        for name in self._path_parts(path):
            folder_created = await self._storage.create_folder(name, parent_uuid)
            parent_uuid = folder_created.uuid

        return parent_uuid

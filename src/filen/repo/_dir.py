from uuid import UUID

from filen.api.models.dir import FolderInfo, FolderUUIDRequestData

from ._base import AsyncRepoBase, RepoBase


class Dir(RepoBase):
    """Dir repository"""

    def info(self, uuid: UUID | None = None) -> FolderInfo:
        uuid = uuid if uuid else self._ensure_base_folder_uuid()
        return self._api.dir.info(FolderUUIDRequestData(uuid=uuid)).data


class AsyncDir(AsyncRepoBase):
    """Async Dir repository"""

    async def info(self, uuid: UUID | None = None) -> FolderInfo:
        uuid = uuid if uuid else (await self._ensure_base_folder_uuid())
        return (await self._api.dir.info(FolderUUIDRequestData(uuid=uuid))).data

from .._base import APIBase, APIEndpoint, AsyncAPIBase
from .models.base import StorageItemUUIDRequestData
from .models.dir import (
    FolderContentRequestData,
    FolderContentResponseData,
    FolderCreateRequestData,
    FolderCreateResponseData,
    FolderDownloadResponseData,
    FolderInfoResponseData,
)


class DirEndpoint(APIEndpoint):
    info = '/dir'
    content = '/dir/content'
    download = '/dir/download'
    create = '/dir/create'


class DirAPI(APIBase):
    """Dir API"""

    def info(self, data: StorageItemUUIDRequestData) -> FolderInfoResponseData:
        return self._post(DirEndpoint.info, data, FolderInfoResponseData)

    def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return self._post(DirEndpoint.content, data, FolderContentResponseData)

    def download(self, data: StorageItemUUIDRequestData) -> FolderDownloadResponseData:
        return self._post(DirEndpoint.download, data, FolderDownloadResponseData)

    def create(self, data: FolderCreateRequestData) -> FolderCreateResponseData:
        return self._post(DirEndpoint.create, data, FolderCreateResponseData)


class AsyncDirAPI(AsyncAPIBase):
    """Async Dir API"""

    async def info(self, data: StorageItemUUIDRequestData) -> FolderInfoResponseData:
        return await self._post(DirEndpoint.info, data, FolderInfoResponseData)

    async def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return await self._post(DirEndpoint.content, data, FolderContentResponseData)

    async def download(self, data: StorageItemUUIDRequestData) -> FolderDownloadResponseData:
        return await self._post(DirEndpoint.download, data, FolderDownloadResponseData)

    async def create(self, data: FolderCreateRequestData) -> FolderCreateResponseData:
        return await self._post(DirEndpoint.create, data, FolderCreateResponseData)

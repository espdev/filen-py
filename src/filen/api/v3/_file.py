from .._base import APIBase, APIEndpoint, AsyncAPIBase
from .models.base import StorageItemExistsRequestData, StorageItemUUIDRequestData
from .models.file import FileExistsResponseData, FileInfoResponseData


class FileEndpoint(APIEndpoint):
    info = '/file'
    exists = '/file/exists'


class FileAPI(APIBase):
    """File API"""

    def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return self._post(FileEndpoint.info, data, FileInfoResponseData)

    def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return self._post(FileEndpoint.exists, data, FileExistsResponseData)


class AsyncFileAPI(AsyncAPIBase):
    """Async File API"""

    async def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return await self._post(FileEndpoint.info, data, FileInfoResponseData)

    async def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return await self._post(FileEndpoint.exists, data, FileExistsResponseData)

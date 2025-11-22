from .._base import APIBase, APIEndpoint, AsyncAPIBase
from .models.base import StorageItemUUIDRequestData
from .models.file import FileInfoResponseData


class FileEndpoint(APIEndpoint):
    info = '/file'


class FileAPI(APIBase):
    """File API"""

    def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return self._post(FileEndpoint.info, data, FileInfoResponseData)


class AsyncFileAPI(AsyncAPIBase):
    """Async File API"""

    async def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return await self._post(FileEndpoint.info, data, FileInfoResponseData)

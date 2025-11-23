from .._base import APIBase, APIEndpoint, AsyncAPIBase
from .models.base import StorageItemExistsRequestData, StorageItemUUIDRequestData
from .models.file import FileExistsResponseData, FileInfoResponseData, FilePublicLinkStatusResponseData


class FileEndpoint(APIEndpoint):
    info = '/file'
    exists = '/file/exists'
    link_status = '/file/link/status'


class FileAPI(APIBase):
    """File API"""

    def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return self._post(FileEndpoint.info, data, FileInfoResponseData)

    def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return self._post(FileEndpoint.exists, data, FileExistsResponseData)

    def link_status(self, data: StorageItemUUIDRequestData) -> FilePublicLinkStatusResponseData:
        return self._post(FileEndpoint.link_status, data, FilePublicLinkStatusResponseData)


class AsyncFileAPI(AsyncAPIBase):
    """Async File API"""

    async def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return await self._post(FileEndpoint.info, data, FileInfoResponseData)

    async def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return await self._post(FileEndpoint.exists, data, FileExistsResponseData)

    async def link_status(self, data: StorageItemUUIDRequestData) -> FilePublicLinkStatusResponseData:
        return await self._post(FileEndpoint.link_status, data, FilePublicLinkStatusResponseData)

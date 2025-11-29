from .._base import APIBase, AsyncAPIBase
from ._base import APIv3Endpoint
from .models.base import ResponseModel, StorageItemExistsRequestData, StorageItemUUIDRequestData
from .models.file import (
    FileExistsResponseData,
    FileInfoResponseData,
    FilePresentResponseData,
    FilePublicLinkEditRequestData,
    FilePublicLinkStatusResponseData,
)


class FileEndpoint(APIv3Endpoint):
    info = '/file'
    present = '/file/present'
    exists = '/file/exists'
    link_status = '/file/link/status'
    link_edit = '/file/link/edit'


class FileAPI(APIBase):
    def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return self._post(FileEndpoint.info, data, FileInfoResponseData)

    def present(self, data: StorageItemUUIDRequestData) -> FilePresentResponseData:
        return self._post(FileEndpoint.present, data, FilePresentResponseData)

    def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return self._post(FileEndpoint.exists, data, FileExistsResponseData)

    def link_status(self, data: StorageItemUUIDRequestData) -> FilePublicLinkStatusResponseData:
        return self._post(FileEndpoint.link_status, data, FilePublicLinkStatusResponseData)

    def link_edit(self, data: FilePublicLinkEditRequestData) -> ResponseModel:
        return self._post(FileEndpoint.link_edit, data, ResponseModel)


class AsyncFileAPI(AsyncAPIBase):
    async def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return await self._post(FileEndpoint.info, data, FileInfoResponseData)

    async def present(self, data: StorageItemUUIDRequestData) -> FilePresentResponseData:
        return await self._post(FileEndpoint.present, data, FilePresentResponseData)

    async def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return await self._post(FileEndpoint.exists, data, FileExistsResponseData)

    async def link_status(self, data: StorageItemUUIDRequestData) -> FilePublicLinkStatusResponseData:
        return await self._post(FileEndpoint.link_status, data, FilePublicLinkStatusResponseData)

    async def link_edit(self, data: FilePublicLinkEditRequestData) -> ResponseModel:
        return await self._post(FileEndpoint.link_edit, data, ResponseModel)

from .._base import APIBase, AsyncAPIBase, api
from ._base import APIv3Endpoint
from ._download import AsyncFileDownloadAPI, FileDownloadAPI
from .models.base import ResponseModel, StorageItemExistsRequestData, StorageItemUUIDRequestData
from .models.file import (
    FileExistsResponseData,
    FileInfoResponseData,
    FileMoveRequestData,
    FilePresentResponseData,
    FilePublicLinkEditRequestData,
    FilePublicLinkStatusResponseData,
    FileRenameRequestData,
)


class FileEndpoint(APIv3Endpoint):
    info = '/file'
    present = '/file/present'
    exists = '/file/exists'
    trash = '/file/trash'
    delete = '/file/delete/permanent'
    move = '/file/move'
    rename = '/file/rename'
    link_status = '/file/link/status'
    link_edit = '/file/link/edit'


class FileAPI(APIBase):
    download: FileDownloadAPI = api(FileDownloadAPI)

    def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return self._post(FileEndpoint.info, data, FileInfoResponseData)

    def present(self, data: StorageItemUUIDRequestData) -> FilePresentResponseData:
        return self._post(FileEndpoint.present, data, FilePresentResponseData)

    def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return self._post(FileEndpoint.exists, data, FileExistsResponseData)

    def trash(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return self._post(FileEndpoint.trash, data, ResponseModel)

    def delete(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return self._post(FileEndpoint.delete, data, ResponseModel)

    def move(self, data: FileMoveRequestData) -> ResponseModel:
        return self._post(FileEndpoint.move, data, ResponseModel)

    def rename(self, data: FileRenameRequestData) -> ResponseModel:
        return self._post(FileEndpoint.rename, data, ResponseModel)

    def link_status(self, data: StorageItemUUIDRequestData) -> FilePublicLinkStatusResponseData:
        return self._post(FileEndpoint.link_status, data, FilePublicLinkStatusResponseData)

    def link_edit(self, data: FilePublicLinkEditRequestData) -> ResponseModel:
        return self._post(FileEndpoint.link_edit, data, ResponseModel)


class AsyncFileAPI(AsyncAPIBase):
    download: AsyncFileDownloadAPI = api(AsyncFileDownloadAPI)

    async def info(self, data: StorageItemUUIDRequestData) -> FileInfoResponseData:
        return await self._post(FileEndpoint.info, data, FileInfoResponseData)

    async def present(self, data: StorageItemUUIDRequestData) -> FilePresentResponseData:
        return await self._post(FileEndpoint.present, data, FilePresentResponseData)

    async def exists(self, data: StorageItemExistsRequestData) -> FileExistsResponseData:
        return await self._post(FileEndpoint.exists, data, FileExistsResponseData)

    async def trash(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return await self._post(FileEndpoint.trash, data, ResponseModel)

    async def delete(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return await self._post(FileEndpoint.delete, data, ResponseModel)

    async def move(self, data: FileMoveRequestData) -> ResponseModel:
        return await self._post(FileEndpoint.move, data, ResponseModel)

    async def rename(self, data: FileRenameRequestData) -> ResponseModel:
        return await self._post(FileEndpoint.rename, data, ResponseModel)

    async def link_status(self, data: StorageItemUUIDRequestData) -> FilePublicLinkStatusResponseData:
        return await self._post(FileEndpoint.link_status, data, FilePublicLinkStatusResponseData)

    async def link_edit(self, data: FilePublicLinkEditRequestData) -> ResponseModel:
        return await self._post(FileEndpoint.link_edit, data, ResponseModel)

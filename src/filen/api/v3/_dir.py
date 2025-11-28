from .._base import APIBase, APIEndpoint, AsyncAPIBase
from .models.base import ResponseModel, StorageItemExistsRequestData, StorageItemUUIDRequestData
from .models.dir import (
    FolderContentRequestData,
    FolderContentResponseData,
    FolderCreateRequestData,
    FolderCreateResponseData,
    FolderDownloadResponseData,
    FolderExistsResponseData,
    FolderInfoResponseData,
    FolderMoveRequestData,
    FolderPublicLinkAddRequestData,
    FolderPublicLinkEditRequestData,
    FolderPublicLinkStatusResponseData,
)


class DirEndpoint(APIEndpoint):
    info = '/dir'
    content = '/dir/content'
    download = '/dir/download'
    exists = '/dir/exists'
    create = '/dir/create'
    link_status = '/dir/link/status'
    link_add = '/dir/link/add'
    link_edit = '/dir/link/edit'
    link_remove = '/dir/link/remove'
    trash = '/dir/trash'
    delete = '/dir/delete/permanent'
    move = '/dir/move'


class DirAPI(APIBase):
    """Dir API"""

    def info(self, data: StorageItemUUIDRequestData) -> FolderInfoResponseData:
        return self._post(DirEndpoint.info, data, FolderInfoResponseData)

    def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return self._post(DirEndpoint.content, data, FolderContentResponseData)

    def download(self, data: StorageItemUUIDRequestData) -> FolderDownloadResponseData:
        return self._post(DirEndpoint.download, data, FolderDownloadResponseData)

    def exists(self, data: StorageItemExistsRequestData) -> FolderExistsResponseData:
        return self._post(DirEndpoint.exists, data, FolderExistsResponseData)

    def create(self, data: FolderCreateRequestData) -> FolderCreateResponseData:
        return self._post(DirEndpoint.create, data, FolderCreateResponseData)

    def trash(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return self._post(DirEndpoint.trash, data, ResponseModel)

    def delete(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return self._post(DirEndpoint.delete, data, ResponseModel)

    def move(self, data: FolderMoveRequestData) -> ResponseModel:
        return self._post(DirEndpoint.move, data, ResponseModel)

    def link_status(self, data: StorageItemUUIDRequestData) -> FolderPublicLinkStatusResponseData:
        return self._post(DirEndpoint.link_status, data, FolderPublicLinkStatusResponseData)

    def link_add(self, data: FolderPublicLinkAddRequestData) -> ResponseModel:
        return self._post(DirEndpoint.link_add, data, ResponseModel)

    def link_edit(self, data: FolderPublicLinkEditRequestData) -> ResponseModel:
        return self._post(DirEndpoint.link_edit, data, ResponseModel)

    def link_remove(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return self._post(DirEndpoint.link_remove, data, ResponseModel)


class AsyncDirAPI(AsyncAPIBase):
    """Async Dir API"""

    async def info(self, data: StorageItemUUIDRequestData) -> FolderInfoResponseData:
        return await self._post(DirEndpoint.info, data, FolderInfoResponseData)

    async def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return await self._post(DirEndpoint.content, data, FolderContentResponseData)

    async def download(self, data: StorageItemUUIDRequestData) -> FolderDownloadResponseData:
        return await self._post(DirEndpoint.download, data, FolderDownloadResponseData)

    async def exists(self, data: StorageItemExistsRequestData) -> FolderExistsResponseData:
        return await self._post(DirEndpoint.exists, data, FolderExistsResponseData)

    async def create(self, data: FolderCreateRequestData) -> FolderCreateResponseData:
        return await self._post(DirEndpoint.create, data, FolderCreateResponseData)

    async def trash(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.trash, data, ResponseModel)

    async def delete(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.delete, data, ResponseModel)

    async def move(self, data: FolderMoveRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.move, data, ResponseModel)

    async def link_status(self, data: StorageItemUUIDRequestData) -> FolderPublicLinkStatusResponseData:
        return await self._post(DirEndpoint.link_status, data, FolderPublicLinkStatusResponseData)

    async def link_add(self, data: FolderPublicLinkAddRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.link_add, data, ResponseModel)

    async def link_edit(self, data: FolderPublicLinkEditRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.link_edit, data, ResponseModel)

    async def link_remove(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.link_remove, data, ResponseModel)

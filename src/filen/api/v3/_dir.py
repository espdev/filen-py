from .._base import APIBase, AsyncAPIBase
from ._base import APIv3Endpoint
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
    FolderPresentResponseData,
    FolderPublicLinkAddRequestData,
    FolderPublicLinkEditRequestData,
    FolderPublicLinkSizeRequestData,
    FolderPublicLinkSizeResponseData,
    FolderPublicLinkStatusResponseData,
    FolderRenameRequestData,
)


class DirEndpoint(APIv3Endpoint):
    info = '/dir'
    content = '/dir/content'
    download = '/dir/download'
    present = '/dir/present'
    exists = '/dir/exists'
    create = '/dir/create'
    trash = '/dir/trash'
    delete = '/dir/delete/permanent'
    move = '/dir/move'
    rename = '/dir/rename'
    empty_trash = '/trash/empty'
    link_status = '/dir/link/status'
    link_size = '/dir/size/link'
    link_add = '/dir/link/add'
    link_edit = '/dir/link/edit'
    link_remove = '/dir/link/remove'


class DirAPI(APIBase):
    def info(self, data: StorageItemUUIDRequestData) -> FolderInfoResponseData:
        return self._post(DirEndpoint.info, data, FolderInfoResponseData)

    def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return self._post(DirEndpoint.content, data, FolderContentResponseData)

    def download(self, data: StorageItemUUIDRequestData) -> FolderDownloadResponseData:
        return self._post(DirEndpoint.download, data, FolderDownloadResponseData)

    def present(self, data: StorageItemUUIDRequestData) -> FolderPresentResponseData:
        return self._post(DirEndpoint.present, data, FolderPresentResponseData)

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

    def rename(self, data: FolderRenameRequestData) -> ResponseModel:
        return self._post(DirEndpoint.rename, data, ResponseModel)

    def empty_trash(self) -> ResponseModel:
        return self._post(DirEndpoint.empty_trash, None, ResponseModel)

    def link_status(self, data: StorageItemUUIDRequestData) -> FolderPublicLinkStatusResponseData:
        return self._post(DirEndpoint.link_status, data, FolderPublicLinkStatusResponseData)

    def link_size(self, data: FolderPublicLinkSizeRequestData) -> FolderPublicLinkSizeResponseData:
        return self._post(DirEndpoint.link_size, data, FolderPublicLinkSizeResponseData)

    def link_add(self, data: FolderPublicLinkAddRequestData) -> ResponseModel:
        return self._post(DirEndpoint.link_add, data, ResponseModel)

    def link_edit(self, data: FolderPublicLinkEditRequestData) -> ResponseModel:
        return self._post(DirEndpoint.link_edit, data, ResponseModel)

    def link_remove(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return self._post(DirEndpoint.link_remove, data, ResponseModel)


class AsyncDirAPI(AsyncAPIBase):
    async def info(self, data: StorageItemUUIDRequestData) -> FolderInfoResponseData:
        return await self._post(DirEndpoint.info, data, FolderInfoResponseData)

    async def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return await self._post(DirEndpoint.content, data, FolderContentResponseData)

    async def download(self, data: StorageItemUUIDRequestData) -> FolderDownloadResponseData:
        return await self._post(DirEndpoint.download, data, FolderDownloadResponseData)

    async def present(self, data: StorageItemUUIDRequestData) -> FolderPresentResponseData:
        return await self._post(DirEndpoint.present, data, FolderPresentResponseData)

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

    async def rename(self, data: FolderRenameRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.rename, data, ResponseModel)

    async def empty_trash(self) -> ResponseModel:
        return await self._post(DirEndpoint.empty_trash, None, ResponseModel)

    async def link_status(self, data: StorageItemUUIDRequestData) -> FolderPublicLinkStatusResponseData:
        return await self._post(DirEndpoint.link_status, data, FolderPublicLinkStatusResponseData)

    async def link_size(self, data: FolderPublicLinkSizeRequestData) -> FolderPublicLinkSizeResponseData:
        return await self._post(DirEndpoint.link_size, data, FolderPublicLinkSizeResponseData)

    async def link_add(self, data: FolderPublicLinkAddRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.link_add, data, ResponseModel)

    async def link_edit(self, data: FolderPublicLinkEditRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.link_edit, data, ResponseModel)

    async def link_remove(self, data: StorageItemUUIDRequestData) -> ResponseModel:
        return await self._post(DirEndpoint.link_remove, data, ResponseModel)

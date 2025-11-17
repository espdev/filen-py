from filen.api.models.dir import (
    FolderContentRequestData,
    FolderContentResponseData,
    FolderInfoResponseData,
    FolderUUIDRequestData,
)

from ._base import APIBase, APIEndpoint, AsyncAPIBase


class DirEndpoint(APIEndpoint):
    info = '/dir'
    content = '/dir/content'


class DirAPI(APIBase):
    def info(self, data: FolderUUIDRequestData) -> FolderInfoResponseData:
        return self._post(DirEndpoint.info, data, FolderInfoResponseData)

    def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return self._post(DirEndpoint.content, data, FolderContentResponseData)


class AsyncDirAPI(AsyncAPIBase):
    async def info(self, data: FolderUUIDRequestData) -> FolderInfoResponseData:
        return await self._post(DirEndpoint.info, data, FolderInfoResponseData)

    async def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return await self._post(DirEndpoint.content, data, FolderContentResponseData)

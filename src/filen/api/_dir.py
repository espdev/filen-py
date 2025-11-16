from filen.api.models.dir import FolderInfoResponseData, FolderUUIDRequestData

from ._base import APIBase, APIEndpoint, AsyncAPIBase


class DirEndpoint(APIEndpoint):
    info = '/dir'
    content = '/dir/content'


class DirAPI(APIBase):
    def info(self, data: FolderUUIDRequestData) -> FolderInfoResponseData:
        return self._post(DirEndpoint.info, data, FolderInfoResponseData)


class AsyncDirAPI(AsyncAPIBase):
    async def info(self, data: FolderUUIDRequestData) -> FolderInfoResponseData:
        return await self._post(DirEndpoint.info, data, FolderInfoResponseData)

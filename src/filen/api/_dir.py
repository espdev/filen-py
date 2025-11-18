from filen.api.models.dir import (
    FolderContentRequestData,
    FolderContentResponseData,
    FolderDownloadResponseData,
    FolderInfoResponseData,
    FolderUUIDRequestData,
)

from ._base import APIBase, APIEndpoint, AsyncAPIBase


class DirEndpoint(APIEndpoint):
    info = '/dir'
    content = '/dir/content'
    download = '/dir/download'


class DirAPI(APIBase):
    def info(self, data: FolderUUIDRequestData) -> FolderInfoResponseData:
        return self._post(DirEndpoint.info, data, FolderInfoResponseData)

    def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return self._post(DirEndpoint.content, data, FolderContentResponseData)

    def download(self, data: FolderUUIDRequestData) -> FolderDownloadResponseData:
        return self._post(DirEndpoint.download, data, FolderDownloadResponseData)


class AsyncDirAPI(AsyncAPIBase):
    async def info(self, data: FolderUUIDRequestData) -> FolderInfoResponseData:
        return await self._post(DirEndpoint.info, data, FolderInfoResponseData)

    async def content(self, data: FolderContentRequestData) -> FolderContentResponseData:
        return await self._post(DirEndpoint.content, data, FolderContentResponseData)

    async def download(self, data: FolderUUIDRequestData) -> FolderDownloadResponseData:
        return await self._post(DirEndpoint.download, data, FolderDownloadResponseData)

from filen._context import Context

from .._base import APIBase, AsyncAPIBase
from ._base import APIv3Endpoint
from .models.file import (
    FileUploadChunkRequestData,
    FileUploadChunkResultResponseData,
    FileUploadDone,
    FileUploadEmpty,
    FileUploadStatusResponseData,
)


class UploadEndpoint(APIv3Endpoint):
    upload = '/upload'
    upload_done = '/upload/done'
    upload_empty = '/upload/empty'


class FileUploadMixIn:
    _context: Context

    def _upload_chunk_url(self) -> str:
        base_url = self._context.get_ingest_url().rstrip('/')
        return f'{base_url}{UploadEndpoint.upload}'


class FileUploadAPI(APIBase, FileUploadMixIn):
    """API for uploading files from the storage"""

    def chunk(self, data: FileUploadChunkRequestData) -> FileUploadChunkResultResponseData:
        """Upload a file chunk to the storage"""

        url = self._upload_chunk_url()

        headers = {'Checksum': data.url_params_hash()}
        headers = self._ensure_headers(use_api_key=True, url=url, headers=headers)

        with self._request_error_handler:
            resp = self._http_client.post(
                url,
                content=data.chunk,
                headers=headers,
                params=data.url_params,
            )
            return FileUploadChunkResultResponseData.from_response(resp)

    def done(self, data: FileUploadDone) -> FileUploadStatusResponseData:
        return self._post(UploadEndpoint.upload_done, data, FileUploadStatusResponseData)

    def empty(self, data: FileUploadEmpty) -> FileUploadStatusResponseData:
        return self._post(UploadEndpoint.upload_empty, data, FileUploadStatusResponseData)


class AsyncFileUploadAPI(AsyncAPIBase, FileUploadMixIn):
    """Async API for uploading files from the storage"""

    async def chunk(self, data: FileUploadChunkRequestData) -> FileUploadChunkResultResponseData:
        """Upload a file chunk to the storage"""

        url = self._upload_chunk_url()

        headers = {'Checksum': data.url_params_hash()}
        headers = self._ensure_headers(use_api_key=True, url=url, headers=headers)

        with self._request_error_handler:
            resp = await self._http_client.post(
                url,
                content=data.chunk,
                headers=headers,
                params=data.url_params,
            )
            return FileUploadChunkResultResponseData.from_response(resp)

    async def done(self, data: FileUploadDone) -> FileUploadStatusResponseData:
        """Marks an upload as completed"""
        return await self._post(UploadEndpoint.upload_done, data, FileUploadStatusResponseData)

    async def empty(self, data: FileUploadEmpty) -> FileUploadStatusResponseData:
        """Upload a placeholder file"""
        return await self._post(UploadEndpoint.upload_empty, data, FileUploadStatusResponseData)

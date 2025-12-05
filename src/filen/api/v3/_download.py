from uuid import UUID

from filen._context import Context
from filen.config import DOWNLOAD_STREAM_CHUNK_SIZE

from .._base import APIBase, AsyncAPIBase


class FileDownloadMixIn:
    _context: Context

    def _download_chunk_url(self, uuid: UUID, bucket: str, region: str, index: int) -> str:
        base_url = self._context.get_egest_url().rstrip('/')
        return f'{base_url}/{region}/{bucket}/{uuid}/{index}'


class FileDownloadAPI(APIBase, FileDownloadMixIn):
    """API for downloading files from the storage"""

    def chunk(self, uuid: UUID, bucket: str, region: str, index: int) -> bytes:
        """Download a file encrypted chunk"""

        url = self._download_chunk_url(uuid, bucket, region, index)
        headers = self._ensure_api_key(use_api_key=True, url=url)

        with self._request_error_handler:
            with self._http_client.stream('GET', url, headers=headers) as resp:
                resp.raise_for_status()
                return b''.join(resp.iter_raw(chunk_size=DOWNLOAD_STREAM_CHUNK_SIZE))


class AsyncFileDownloadAPI(AsyncAPIBase, FileDownloadMixIn):
    """Async API for downloading files from the storage"""

    async def chunk(self, uuid: UUID, bucket: str, region: str, index: int) -> bytes:
        """Download a file encrypted chunk"""

        url = self._download_chunk_url(uuid, bucket, region, index)
        headers = self._ensure_api_key(use_api_key=True, url=url)

        with self._request_error_handler:
            async with self._http_client.stream('GET', url, headers=headers) as resp:
                resp.raise_for_status()
                buffer = bytearray()
                async for c in resp.aiter_raw(chunk_size=DOWNLOAD_STREAM_CHUNK_SIZE):
                    buffer.extend(c)
                return bytes(buffer)

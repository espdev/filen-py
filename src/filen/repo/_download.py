from asyncio import CancelledError
from collections.abc import AsyncIterator, Iterator
import logging
import time

import anyio
from humanize import naturaldelta, naturalsize

from filen._logging import logger
from filen.config import UPLOAD_CHUNK_SIZE
from filen.crypto import decrypt_content

from ._base import AsyncRepoBase, RepoBase
from .models import FileInfo

DEBUG_PRINT_INTERVAL = 50


def calc_chunk_range(start: int, end: int, chunk_count: int) -> tuple[int, int]:
    """Calculate [first, last] chunk indices for given [start, end] bytes range"""

    first = start // UPLOAD_CHUNK_SIZE
    last = end // UPLOAD_CHUNK_SIZE

    first = max(0, first)
    last = min(chunk_count - 1, last)

    return first, last


class FileDownload(RepoBase):
    """Downloading files from the storage"""

    def stream(
        self,
        file_info: FileInfo,
        start: int | None = None,
        end: int | None = None,
    ) -> Iterator[bytes]:
        """Streaming file download"""

        # first, last = calc_chunk_range(start, end, file_info.chunks)
        # chunks_to_download = last - first + 1
        # is_entire_file = chunks_to_download == file_info.chunks
        #
        # for chunk in range(first, last):
        #     pass

    def _fetch_and_decrypt_chunk(self, file_info: FileInfo, chunk: int) -> bytes:
        data = self._api.v3.file.download.chunk(
            uuid=file_info.uuid,
            bucket=file_info.bucket,
            region=file_info.region,
            chunk=chunk,
        )

        return decrypt_content(
            data=data,
            key=file_info.metadata.key,
            version=file_info.version,
        )


class AsyncChunkBuffer:
    """A buffer and synchronization primitive for coordinating concurrent chunk processing"""

    def __init__(self, first: int, last: int, backpressure: int):
        self._next_chunk_index = first
        self._last = last
        self._counter_lock = anyio.Lock()
        self._condition = anyio.Condition()
        self._backpressure = backpressure
        self._chunk_buffer: dict[int, bytes] = {}

    async def get_next_index(self) -> int | None:
        async with self._counter_lock:
            if self._next_chunk_index > self._last:
                return None
            index = self._next_chunk_index
            self._next_chunk_index += 1
            return index

    async def add_chunk(self, index: int, data: bytes) -> None:
        async with self._condition:
            # backpressure control
            while len(self._chunk_buffer) >= self._backpressure:
                # waiting for a consumer to pick up the chunks
                await self._condition.wait()

            self._chunk_buffer[index] = data
            self._condition.notify_all()

    async def pop_chunk(self, index: int) -> bytes | None:
        async with self._condition:
            while index not in self._chunk_buffer:
                await self._condition.wait()

            data = self._chunk_buffer.pop(index, None)
            self._condition.notify_all()
            return data


class AsyncFileDownloadController:
    """Control async downloading file process"""

    def __init__(self, autostart: bool = True):
        self._start_event = anyio.Event()
        self._pause_event = anyio.Event()
        self._is_cancelled = False
        self._autostart = autostart

        if autostart:
            self._start_event.set()
        self._pause_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def start(self):
        self._start_event.set()
        self._pause_event.set()

    def pause(self):
        if self._pause_event.is_set():
            self._pause_event = anyio.Event()

    def cancel(self):
        self._is_cancelled = True
        self.start()

    def reset(self):
        self._start_event = anyio.Event()
        self._pause_event = anyio.Event()
        self._is_cancelled = False

        if self._autostart:
            self._start_event.set()
        self._pause_event.set()

    async def wait_for_start(self):
        await self._start_event.wait()

    async def wait_for_pause(self):
        await self._pause_event.wait()

    def raise_for_cancelled(self, cancel_scope: anyio.CancelScope | None = None):
        if self._is_cancelled:
            msg = 'Cancelled by download controller'
            if cancel_scope:
                cancel_scope.cancel(msg)
            else:
                raise CancelledError(msg)


class AsyncFileDownload(AsyncRepoBase):
    """Async downloading files from the storage"""

    async def stream(
        self,
        file_info: FileInfo,
        *,
        start: int | None = None,
        end: int | None = None,
        controller: AsyncFileDownloadController | None = None,
    ) -> AsyncIterator[bytes]:
        """Streaming file download"""

        if start is None:
            start = 0
        if end is None:
            end = file_info.metadata.size - 1

        if start < 0:
            raise ValueError('start must be >= 0')
        if end >= file_info.metadata.size:
            raise ValueError(f'end must be < {file_info.metadata.size}')
        if start > end:
            raise ValueError('start must be <= end')

        if not controller:
            controller = AsyncFileDownloadController()

        await controller.wait_for_start()
        controller.raise_for_cancelled()

        first, last = calc_chunk_range(start, end, file_info.chunks)
        num_chunks_to_download = last - first + 1
        is_entire_file = num_chunks_to_download == file_info.chunks

        chunk_buffer = AsyncChunkBuffer(
            first=first,
            last=last,
            backpressure=self._context.download_chunks_backpressure,
        )

        logger.debug(
            '%d/%d [%d..%d] chunks will be downloaded for file %r <%s>',
            num_chunks_to_download,
            file_info.chunks,
            first,
            last,
            file_info.metadata.name,
            file_info.uuid,
        )

        async with self._context.async_concurrent_downloads_semaphore:
            controller.raise_for_cancelled()

            ts = time.monotonic()
            chunk_count = 0
            byte_count = 0

            try:
                async with self._runner.task_group() as tg:
                    for w_id in range(self._context.download_chunks_concurrency):
                        tg.add_task(w_id, self._worker, file_info, chunk_buffer, w_id)

                    for i, index in enumerate(range(first, last + 1), start=1):
                        await controller.wait_for_pause()
                        controller.raise_for_cancelled(tg.cancel_scope)

                        chunk_data = await chunk_buffer.pop_chunk(index)
                        if chunk_data is None:
                            logger.error("Chunk data is None. That shouldn't happen.")
                            continue

                        chunk_count += 1
                        byte_count += len(chunk_data)

                        if logger.isEnabledFor(logging.DEBUG) and i % DEBUG_PRINT_INTERVAL == 0:
                            took = time.monotonic() - ts
                            logger.debug(
                                'File %r <%s>: %.1f%%, %d/%d chunks, %s/%s, %s/s',
                                file_info.metadata.name,
                                file_info.uuid,
                                i / num_chunks_to_download * 100,
                                i,
                                num_chunks_to_download,
                                naturalsize(byte_count, binary=True),
                                naturalsize(file_info.metadata.size, binary=True),
                                naturalsize(byte_count / took, binary=True),
                            )

                        if not is_entire_file:
                            chunk_start_offset = index * UPLOAD_CHUNK_SIZE
                            start_offset = 0
                            end_offset = len(chunk_data)

                            if index == first:
                                start_offset = max(0, start - chunk_start_offset)
                            if index == last:
                                end_offset = min(len(chunk_data), end - chunk_start_offset + 1)

                            chunk_data = chunk_data[start_offset:end_offset]

                        yield chunk_data

            except* CancelledError as e:
                msg = 'Download file {name!r} <{uuid}> was cancelled at {pct:.1f}%, {count}/{total} chunks'.format(
                    name=file_info.metadata.name,
                    uuid=file_info.uuid,
                    pct=chunk_count / num_chunks_to_download * 100,
                    count=chunk_count,
                    total=num_chunks_to_download,
                )
                logger.warning(msg)
                raise CancelledError(msg) from e
            else:
                took = time.monotonic() - ts

                logger.debug(
                    'Download file %r <%s> completed [ET: %s, %s, %s/s]',
                    file_info.metadata.name,
                    file_info.uuid,
                    naturaldelta(took),
                    naturalsize(byte_count, binary=True),
                    naturalsize(byte_count / took, binary=True),
                )

    async def _worker(self, file_info: FileInfo, chunk_buffer: AsyncChunkBuffer, worker_id: int) -> int:
        """Download and decrypt file chunks"""

        logger.debug('Starting worker %d for file %r <%s>', worker_id, file_info.metadata.name, file_info.uuid)
        chunk_count = 0
        byte_count = 0
        ts = time.monotonic()

        while True:
            index = await chunk_buffer.get_next_index()
            if index is None:
                break

            data_enc = await self._api.v3.file.download.chunk(file_info.uuid, file_info.bucket, file_info.region, index)
            data = await self._runner.run_sync(decrypt_content, data_enc, file_info.metadata.key, file_info.version)

            chunk_count += 1
            byte_count += len(data)

            await chunk_buffer.add_chunk(index, data)

        took = time.monotonic() - ts
        speed = byte_count / took

        logger.debug(
            'Finishing worker %d for file %r <%s> [%d chunks, %s/s]',
            worker_id,
            file_info.metadata.name,
            file_info.uuid,
            chunk_count,
            naturalsize(speed, binary=True),
        )

        return chunk_count

import asyncio
from collections.abc import AsyncIterator, Iterator
import logging
import threading
import time

import anyio
from humanize import naturaldelta, naturalsize

from filen._logging import logger
from filen.config import UPLOAD_CHUNK_SIZE
from filen.crypto import decrypt_content
from filen.errors import DownloadCancelled, DownloadError

from ._base import AsyncRepoBase, RepoBase
from .models import FileInfo

DEBUG_PRINT_INTERVAL = 50


def _calc_chunk_range(start: int, end: int, chunk_count: int) -> tuple[int, int]:
    """Calculate [first, last] chunk indices for given [start, end] bytes range"""

    first = start // UPLOAD_CHUNK_SIZE
    last = end // UPLOAD_CHUNK_SIZE

    first = max(0, first)
    last = min(chunk_count - 1, last)

    return first, last


class FileDownloadController:
    """Control sync downloading file process"""

    def __init__(self, autostart: bool = True):
        self._start_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_cancelled = False
        self._autostart = autostart

        if autostart:
            self._start_event.set()
        self._pause_event.set()

    @property
    def is_cancelled(self) -> bool:
        """Return True if the downloading process was cancelled"""
        return self._is_cancelled

    def start(self):
        """Start/resume downloading process"""
        self._start_event.set()
        self._pause_event.set()

    def pause(self):
        """Pause downloading process"""
        self._pause_event.clear()

    def cancel(self):
        """Cancel downloading process (interrupt downloading)"""
        self._is_cancelled = True
        self.start()

    def reset(self):
        """Reset the controller state"""
        self._start_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_cancelled = False

        if self._autostart:
            self._start_event.set()
        self._pause_event.set()

    def wait_for_start(self):
        """Wait for start (called in the downloader)"""
        self._start_event.wait()

    def wait_for_resume(self):
        """Wait for resume after pause (called in the downloader)"""
        self._pause_event.wait()

    def raise_for_cancellation(self, *_):
        """Raise DownloadCancelled if the downloading process was cancelled"""
        if self._is_cancelled:
            raise DownloadCancelled('Cancelled by download controller')


class FileDownload(RepoBase):
    """Downloading files from the storage"""

    def stream(
        self,
        file_info: FileInfo,
        *,
        start: int | None = None,
        end: int | None = None,
        controller: FileDownloadController | None = None,
    ) -> Iterator[bytes]:
        """Streaming file download"""

        raise NotImplementedError


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

    async def clear(self):
        async with self._condition:
            self._chunk_buffer.clear()
            self._condition.notify_all()


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
        """Return True if the downloading process was cancelled"""
        return self._is_cancelled

    def start(self):
        """Start/resume downloading process"""
        self._start_event.set()
        self._pause_event.set()

    def pause(self):
        """Pause downloading process"""
        if self._pause_event.is_set():
            self._pause_event = anyio.Event()

    def cancel(self):
        """Cancel downloading process (interrupt downloading)"""
        self._is_cancelled = True
        self.start()

    def reset(self):
        """Reset the controller state"""
        self._start_event = anyio.Event()
        self._pause_event = anyio.Event()
        self._is_cancelled = False

        if self._autostart:
            self._start_event.set()
        self._pause_event.set()

    async def wait_for_start(self):
        """Wait for start

        Called in the downloader
        """
        await self._start_event.wait()

    async def wait_for_resume(self):
        """Wait for resume after pause

        Called in the downloader
        """
        await self._pause_event.wait()

    def raise_for_cancellation(self, cancel_scope: anyio.CancelScope | None = None):
        """Raise DownloadCancelled or call cancel_scope if the downloading process was cancelled

        Called in the downloader
        """
        if self._is_cancelled:
            msg = 'Cancelled by download controller'
            if cancel_scope:
                cancel_scope.cancel(msg)
            else:
                raise DownloadCancelled(msg)


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
        controller.raise_for_cancellation()

        first, last = _calc_chunk_range(start, end, file_info.chunks)
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
            controller.raise_for_cancellation()

            ts = time.monotonic()
            chunk_count = 0
            byte_count = 0

            try:
                async with self._runner.task_group() as tg:
                    for w_id in range(self._context.download_chunks_concurrency):
                        tg.add_task(w_id, self._worker, file_info, controller, chunk_buffer, w_id)

                    for i, index in enumerate(range(first, last + 1), start=1):
                        await controller.wait_for_resume()
                        controller.raise_for_cancellation(tg.cancel_scope)

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

            except* asyncio.CancelledError as exc_gr:
                await chunk_buffer.clear()

                pct = chunk_count / num_chunks_to_download * 100
                msg = (
                    f'Downloading file {file_info.metadata.name!r} <{file_info.uuid}> was cancelled at {pct:.1f}%, '
                    f'{chunk_count}/{num_chunks_to_download} chunks'
                )
                logger.warning(msg)
                raise DownloadCancelled(msg) from exc_gr

            except* Exception as exc_gr:
                await chunk_buffer.clear()

                raise DownloadError(
                    f'Downloading file {file_info.metadata.name!r} <{file_info.uuid}> has failed.'
                ) from exc_gr

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

    async def _worker(
        self,
        file_info: FileInfo,
        controller: AsyncFileDownloadController,
        chunk_buffer: AsyncChunkBuffer,
        worker_id: int,
    ) -> int:
        """Download and decrypt file chunks"""

        logger.debug('Starting worker %d for file %r <%s>', worker_id, file_info.metadata.name, file_info.uuid)
        chunk_count = 0
        byte_count = 0
        ts = time.monotonic()

        while not controller.is_cancelled:
            await controller.wait_for_resume()

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

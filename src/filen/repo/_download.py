from typing import Awaitable, Callable
import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
import logging
import time

import anyio
from anyio import to_thread
from humanize import naturaldelta, naturalsize

from filen._controller import (
    AsyncFileDownloadUploadController,
    DownloadUploadState,
    DownloadUploadStatusBase,
    FileDownloadUploadController,
)
from filen._logging import logger
from filen.config import DEBUG_PRINT_INTERVAL, UPLOAD_CHUNK_SIZE
from filen.crypto import decrypt_content
from filen.errors import DownloadCancelled, DownloadError

from ._base import AsyncRepoBase, RepoBase
from .models import FileInfo


def _calc_chunk_range(start: int, end: int, chunk_count: int) -> tuple[int, int]:
    """Calculate [first, last] chunk indices for given [start, end] bytes range"""

    first = start // UPLOAD_CHUNK_SIZE
    last = end // UPLOAD_CHUNK_SIZE

    first = max(0, first)
    last = min(chunk_count - 1, last)

    return first, last


@dataclass(slots=True, frozen=True, kw_only=True)
class DownloadStatus(DownloadUploadStatusBase):
    file_info: FileInfo
    start: int
    end: int


type DownloadStatusCallback = Callable[[DownloadStatus], None]
type AsyncDownloadStatusCallback = Callable[[DownloadStatus], None | Awaitable[None]]


class FileDownload(RepoBase):
    """Downloading files from the storage"""

    def stream(
        self,
        file_info: FileInfo,
        *,
        start: int | None = None,
        end: int | None = None,
        status_callback: DownloadStatusCallback | None = None,
        controller: FileDownloadUploadController | None = None,
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


class AsyncFileDownload(AsyncRepoBase):
    """Async downloading files from the storage"""

    async def stream(
        self,
        file_info: FileInfo,
        *,
        start: int | None = None,
        end: int | None = None,
        status_callback: AsyncDownloadStatusCallback | None = None,
        controller: AsyncFileDownloadUploadController | None = None,
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
            controller = AsyncFileDownloadUploadController()

        await controller.wait_for_start()

        first, last = _calc_chunk_range(start, end, file_info.chunks)
        num_chunks_to_download = last - first + 1
        is_entire_file = num_chunks_to_download == file_info.chunks

        if controller.is_cancelled:
            await self._on_status(
                status_callback,
                file_info=file_info,
                controller=controller,
                state=DownloadUploadState.cancelled,
                start=start,
                end=end,
                num_chunks=num_chunks_to_download,
            )
        controller.raise_for_cancellation(DownloadCancelled)

        chunk_buffer = AsyncChunkBuffer(
            first=first,
            last=last,
            backpressure=self._context.download_chunks_backpressure,
        )

        logger.debug(
            '%d/%d [%d..%d] chunks will be downloaded for file %r <%s> %s',
            num_chunks_to_download,
            file_info.chunks,
            first,
            last,
            file_info.metadata.name,
            file_info.uuid,
            naturalsize(file_info.metadata.size, binary=True),
        )

        await self._on_status(
            status_callback,
            file_info=file_info,
            controller=controller,
            state=DownloadUploadState.queued,
            start=start,
            end=end,
            num_chunks=num_chunks_to_download,
        )

        async with self._context.async_concurrent_downloads_semaphore:
            if controller.is_cancelled:
                await self._on_status(
                    status_callback,
                    file_info=file_info,
                    controller=controller,
                    state=DownloadUploadState.cancelled,
                    start=start,
                    end=end,
                    num_chunks=num_chunks_to_download,
                )
            controller.raise_for_cancellation(DownloadCancelled)

            ts = time.monotonic()
            chunk_count = 0
            byte_count = 0

            try:
                async with self._runner.task_group() as tg:
                    await self._on_status(
                        status_callback,
                        file_info=file_info,
                        controller=controller,
                        state=DownloadUploadState.started,
                        start=start,
                        end=end,
                        num_chunks=num_chunks_to_download,
                    )

                    for w_id in range(self._context.download_chunks_concurrency):
                        tg.add_task(w_id, self._worker, file_info, controller, chunk_buffer, w_id)

                    for index in range(first, last + 1):
                        if controller.is_paused:
                            await self._on_status(
                                status_callback,
                                file_info=file_info,
                                controller=controller,
                                state=DownloadUploadState.paused,
                                start=start,
                                end=end,
                                num_chunks=num_chunks_to_download,
                                chunk_count=chunk_count,
                                byte_count=byte_count,
                            )
                        await controller.wait_for_resume()
                        controller.raise_for_cancellation(tg.cancel_scope)

                        chunk_data = await chunk_buffer.pop_chunk(index)
                        if chunk_data is None:
                            logger.error("Chunk data is None. That shouldn't happen.")
                            continue

                        if not is_entire_file:
                            chunk_start_offset = index * UPLOAD_CHUNK_SIZE
                            start_offset = 0
                            end_offset = len(chunk_data)

                            if index == first:
                                start_offset = max(0, start - chunk_start_offset)
                            if index == last:
                                end_offset = min(len(chunk_data), end - chunk_start_offset + 1)

                            chunk_data = chunk_data[start_offset:end_offset]

                        chunk_count += 1
                        byte_count += len(chunk_data)

                        await self._on_status(
                            status_callback,
                            file_info=file_info,
                            controller=controller,
                            state=DownloadUploadState.in_progress,
                            start=start,
                            end=end,
                            num_chunks=num_chunks_to_download,
                            chunk_count=chunk_count,
                            byte_count=byte_count,
                        )

                        if logger.isEnabledFor(logging.DEBUG) and chunk_count % DEBUG_PRINT_INTERVAL == 0:
                            took = time.monotonic() - ts
                            logger.debug(
                                'Download file %r <%s>: %.1f%%, %d/%d chunks, %s, %s/s',
                                file_info.metadata.name,
                                file_info.uuid,
                                chunk_count / num_chunks_to_download * 100,
                                chunk_count,
                                num_chunks_to_download,
                                naturalsize(byte_count, binary=True),
                                naturalsize(byte_count / took, binary=True),
                            )

                        yield chunk_data

            except* asyncio.CancelledError as exc_gr:
                await chunk_buffer.clear()

                pct = chunk_count / num_chunks_to_download * 100
                msg = (
                    f'Downloading file {file_info.metadata.name!r} <{file_info.uuid}> was cancelled at {pct:.1f}%, '
                    f'{chunk_count}/{num_chunks_to_download} chunks'
                )

                await self._on_status(
                    status_callback,
                    file_info=file_info,
                    controller=controller,
                    state=DownloadUploadState.cancelled,
                    start=start,
                    end=end,
                    num_chunks=num_chunks_to_download,
                    chunk_count=chunk_count,
                    byte_count=byte_count,
                )
                raise DownloadCancelled(msg) from exc_gr

            except* Exception as exc_gr:
                await chunk_buffer.clear()
                await self._on_status(
                    status_callback,
                    file_info=file_info,
                    controller=controller,
                    state=DownloadUploadState.failed,
                    start=start,
                    end=end,
                    num_chunks=num_chunks_to_download,
                    chunk_count=chunk_count,
                    byte_count=byte_count,
                    error=exc_gr,
                )

                raise DownloadError(
                    f'Downloading file {file_info.metadata.name!r} <{file_info.uuid}> has failed: '
                    f'{exc_gr.exceptions[0]}'
                ) from exc_gr

            took = time.monotonic() - ts

            logger.debug(
                'Download file %r <%s> completed [ET: %s, %s, %s/s]',
                file_info.metadata.name,
                file_info.uuid,
                naturaldelta(took),
                naturalsize(byte_count, binary=True),
                naturalsize(byte_count / took, binary=True),
            )

            await self._on_status(
                status_callback,
                file_info=file_info,
                controller=controller,
                state=DownloadUploadState.done,
                start=start,
                end=end,
                num_chunks=num_chunks_to_download,
                chunk_count=chunk_count,
                byte_count=byte_count,
            )

    async def _worker(
        self,
        file_info: FileInfo,
        controller: AsyncFileDownloadUploadController,
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

    @staticmethod
    async def _on_status(
        callback: AsyncDownloadStatusCallback | None,
        file_info: FileInfo,
        controller: AsyncFileDownloadUploadController,
        state: DownloadUploadState,
        start: int,
        end: int,
        num_chunks: int,
        chunk_count: int = 0,
        byte_count: int = 0,
        error: ExceptionGroup | None = None,
    ) -> None:
        if not callback:
            return
        try:
            status = DownloadStatus(
                file_info=file_info,
                controller=controller,
                state=state,
                start=start,
                end=end,
                num_chunks=num_chunks,
                chunk_count=chunk_count,
                byte_count=byte_count,
                error=error,
            )

            if asyncio.iscoroutinefunction(callback):
                await callback(status)
            else:
                await to_thread.run_sync(callback, status)
        except Exception as e:
            logger.exception('An error occurred in download status callback: %s', e)

from typing import IO, AsyncIterator, Awaitable, BinaryIO, Callable, TypedDict, cast
import asyncio
from dataclasses import dataclass
import logging
import math
from mimetypes import guess_type
from os import PathLike
import time
from uuid import UUID, uuid4

import anyio
from anyio.abc import ObjectReceiveStream
from anyio.streams.file import EndOfStream, FileReadStream
from humanize import naturaldelta, naturalsize

from filen._controller import (
    AsyncFileDownloadUploadController,
    DownloadUploadState,
    DownloadUploadStatusBase,
    FileDownloadUploadController,
)
from filen._logging import logger
from filen.api.v3.models.file import FileUploadChunkRequestData, FileUploadDone
from filen.config import (
    DEBUG_PRINT_INTERVAL,
    DEFAULT_UPLOAD_BUCKET,
    DEFAULT_UPLOAD_REGION,
    FALLBACK_MIME_TYPE,
    FILE_ENCRYPTION_VERSION,
    UPLOAD_CHUNK_SIZE,
)
from filen.crypto import (
    data_hasher,
    encrypt_content,
    encrypt_metadata,
    encrypt_metadata_model,
    generate_file_encryption_key,
    generate_rm,
    generate_upload_key,
    hash_data,
    hash_file,
    hash_name,
)
from filen.errors import UploadCancelled, UploadError

from ._base import AsyncRepoBase, RepoBase, repo
from ._lock import AsyncLock, LockResource
from .models import FileMetadata

type File = IO[bytes] | BinaryIO | anyio.AsyncFile
type ItemId = UUID | str
type ChunkItemToUpload = tuple[int, bytes]


class UploadInfo(TypedDict):
    chunk_count: int
    byte_count: int
    bucket: str
    region: str


@dataclass(slots=True, frozen=True, kw_only=True)
class UploadStatus(DownloadUploadStatusBase):
    uuid: UUID
    metadata: FileMetadata


type UploadStatusCallback = Callable[[UploadStatus], None]
type AsyncUploadStatusCallback = Callable[[UploadStatus], None | Awaitable[None]]


class FileUpload(RepoBase):
    """Uploading files to the storage"""

    async def from_path(
        self,
        path: PathLike | str,
        parent: ItemId | None = None,
        *,
        status_callback: UploadStatusCallback | None = None,
        controller: FileDownloadUploadController | None = None,
    ) -> UUID:
        """Upload a file from local filesystem path"""

        raise NotImplementedError

    async def from_file(
        self,
        file: File,
        metadata: FileMetadata,
        parent: ItemId | None = None,
        *,
        status_callback: UploadStatusCallback | None = None,
        controller: FileDownloadUploadController | None = None,
    ) -> UUID:
        """Upload a file from BinaryIO object and the file metadata"""

        raise NotImplementedError


class AsyncFileUpload(AsyncRepoBase):
    """Async uploading files to the storage"""

    _drive_write_lock: AsyncLock = repo(AsyncLock, resource=LockResource.drive_write)

    async def from_path(
        self,
        path: PathLike | str,
        parent: ItemId | None = None,
        *,
        status_callback: AsyncUploadStatusCallback | None = None,
        controller: AsyncFileDownloadUploadController | None = None,
    ) -> UUID:
        """Upload a file from local filesystem path"""

        apath = anyio.Path(path)

        if not await apath.is_file():
            raise UploadError(f'File {apath} does not exist.')

        stat = await apath.stat()
        mime = guess_type(path)[0] or FALLBACK_MIME_TYPE

        metadata = FileMetadata(
            name=apath.name,
            size=stat.st_size,
            mime=mime,
            key='',
            hash=hash_file(apath),
            created=round(stat.st_ctime_ns / 1e6),
            last_modified=round(stat.st_mtime_ns / 1e6),
        )

        async with await anyio.open_file(apath, 'rb') as file:
            return await self.from_file(file, metadata, parent, controller=controller, status_callback=status_callback)

    async def from_file(
        self,
        file: File,
        metadata: FileMetadata,
        parent: ItemId | None = None,
        *,
        status_callback: AsyncUploadStatusCallback | None = None,
        controller: AsyncFileDownloadUploadController | None = None,
    ) -> UUID:
        """Upload a file from BinaryIO object and the file metadata"""

        if isinstance(file, anyio.AsyncFile):
            file = file.wrapped
        file = cast(BinaryIO, file)

        async with FileReadStream(file) as stream:
            return await self.from_stream(
                stream, metadata, parent, controller=controller, status_callback=status_callback
            )

    async def from_stream(
        self,
        stream: FileReadStream,
        metadata: FileMetadata,
        parent: ItemId | None = None,
        *,
        status_callback: AsyncUploadStatusCallback | None = None,
        controller: AsyncFileDownloadUploadController | None = None,
    ) -> UUID:
        """Upload a file from FileReadStream object and the file metadata"""

        master_key = await self._ensure_master_key()

        if not controller:
            controller = AsyncFileDownloadUploadController()

        await controller.wait_for_start()

        metadata = metadata.model_copy()
        metadata.key = await self._runner.run_sync(generate_file_encryption_key)
        num_chunks = math.ceil(metadata.size / UPLOAD_CHUNK_SIZE)
        is_calc_file_hash = not bool(metadata.hash)
        file_hasher = data_hasher()

        file_uuid = uuid4()

        if controller.is_cancelled:
            await self._on_status(
                status_callback,
                file_uuid=file_uuid,
                metadata=metadata,
                controller=controller,
                state=DownloadUploadState.cancelled,
                num_chunks=num_chunks,
            )
        controller.raise_for_cancellation(UploadCancelled)

        await self._on_status(
            status_callback,
            file_uuid=file_uuid,
            metadata=metadata,
            controller=controller,
            state=DownloadUploadState.queued,
            num_chunks=num_chunks,
        )

        async with self._context.async_concurrent_uploads_semaphore:
            if controller.is_cancelled:
                await self._on_status(
                    status_callback,
                    file_uuid=file_uuid,
                    metadata=metadata,
                    controller=controller,
                    state=DownloadUploadState.cancelled,
                    num_chunks=num_chunks,
                )
            controller.raise_for_cancellation(UploadCancelled)

            parent = parent or (await self._ensure_base_folder_uuid())
            upload_key = await self._runner.run_sync(generate_upload_key)

            chunk_send_stream, chunk_receive_stream = anyio.create_memory_object_stream[ChunkItemToUpload](
                max_buffer_size=self._context.upload_chunks_concurrency
            )

            upload_info: UploadInfo = {
                'chunk_count': 0,
                'byte_count': 0,
                'bucket': DEFAULT_UPLOAD_BUCKET,
                'region': DEFAULT_UPLOAD_REGION,
            }
            upload_info_lock = anyio.Lock()

            logger.debug(
                'Uploading file %r <%s> %s in %d chunks ...',
                metadata.name,
                file_uuid,
                naturalsize(metadata.size, binary=True),
                num_chunks,
            )
            ts = time.monotonic()

            try:
                async with self._runner.task_group() as tg:
                    await self._on_status(
                        status_callback,
                        file_uuid=file_uuid,
                        metadata=metadata,
                        controller=controller,
                        state=DownloadUploadState.started,
                        num_chunks=num_chunks,
                    )

                    for w_id in range(self._context.upload_chunks_concurrency):
                        tg.add_task(
                            w_id,
                            self._worker,
                            receive_stream=chunk_receive_stream.clone(),
                            file_uuid=file_uuid,
                            parent=parent,
                            upload_key=upload_key,
                            num_chunks=num_chunks,
                            metadata=metadata,
                            upload_info=upload_info,
                            upload_info_lock=upload_info_lock,
                            status_callback=status_callback,
                            controller=controller,
                            ts=ts,
                        )

                    async with chunk_send_stream:
                        async for index, chunk in self._streaming_chunks(stream):
                            if controller.is_paused:
                                async with upload_info_lock:
                                    await self._on_status(
                                        status_callback,
                                        file_uuid=file_uuid,
                                        metadata=metadata,
                                        controller=controller,
                                        state=DownloadUploadState.paused,
                                        num_chunks=num_chunks,
                                        chunk_count=upload_info['chunk_count'],
                                        byte_count=upload_info['byte_count'],
                                    )
                            await controller.wait_for_resume()
                            controller.raise_for_cancellation(tg.cancel_scope)

                            if is_calc_file_hash:
                                await anyio.to_thread.run_sync(file_hasher.update, chunk)

                            await chunk_send_stream.send((index, chunk))

            except* asyncio.CancelledError as exc_gr:
                await self._on_status(
                    status_callback,
                    file_uuid=file_uuid,
                    metadata=metadata,
                    controller=controller,
                    state=DownloadUploadState.cancelled,
                    num_chunks=num_chunks,
                    chunk_count=upload_info['chunk_count'],
                    byte_count=upload_info['byte_count'],
                )
                raise UploadCancelled(f'Uploading file {metadata.name!r} <{file_uuid}> cancelled.') from exc_gr

            except* Exception as exc_gr:
                await self._on_status(
                    status_callback,
                    file_uuid=file_uuid,
                    metadata=metadata,
                    controller=controller,
                    state=DownloadUploadState.failed,
                    num_chunks=num_chunks,
                    chunk_count=upload_info['chunk_count'],
                    byte_count=upload_info['byte_count'],
                    error=exc_gr,
                )
                raise UploadError(
                    f'Uploading file {metadata.name!r} <{file_uuid}> has failed: {exc_gr.exceptions[0]}'
                ) from exc_gr

            if is_calc_file_hash:
                metadata.hash = file_hasher.hexdigest()

            rm = await self._runner.run_sync(generate_rm)

            async with self._runner.task_group() as tg:
                tg.add_task('name_enc', encrypt_metadata, metadata.name, metadata.key)
                tg.add_task('mime_enc', encrypt_metadata, metadata.mime, metadata.key)
                tg.add_task('size_enc', encrypt_metadata, str(metadata.size), metadata.key)
                tg.add_task('metadata_enc', encrypt_metadata_model, metadata, master_key)
                tg.add_task('name_hashed', hash_name, metadata.name, self._context.auth_version)

            done_data = FileUploadDone(
                uuid=file_uuid,
                name=tg.results['name_enc'],
                name_hashed=tg.results['name_hashed'],
                mime=tg.results['mime_enc'],
                size=tg.results['size_enc'],
                metadata=tg.results['metadata_enc'],
                version=FILE_ENCRYPTION_VERSION,
                rm=rm,
                chunks=num_chunks,
                upload_key=upload_key,
            )

            async with self._drive_write_lock:
                result = (await self._api.v3.file.upload.done(done_data)).data

            took = time.monotonic() - ts
            logger.debug(
                'Upload file %r <%s> completed [ET: %s, %s, %s/s]',
                metadata.name,
                file_uuid,
                naturaldelta(took),
                naturalsize(result.size, binary=True),
                naturalsize(result.size / took, binary=True),
            )

            # TODO: add the file to folder publink link is needed

            await self._on_status(
                status_callback,
                file_uuid=file_uuid,
                metadata=metadata,
                controller=controller,
                state=DownloadUploadState.done,
                num_chunks=num_chunks,
                chunk_count=upload_info['chunk_count'],
                byte_count=upload_info['byte_count'],
            )

        return file_uuid

    @staticmethod
    async def _streaming_chunks(stream: FileReadStream) -> AsyncIterator[tuple[int, bytes]]:
        index = 0
        while True:
            try:
                yield index, (await stream.receive(UPLOAD_CHUNK_SIZE))
            except EndOfStream:
                break
            index += 1

    async def _worker(
        self,
        receive_stream: ObjectReceiveStream[ChunkItemToUpload],
        file_uuid: UUID,
        parent: ItemId,
        upload_key: str,
        num_chunks: int,
        metadata: FileMetadata,
        upload_info: UploadInfo,
        upload_info_lock: anyio.Lock,
        status_callback: AsyncUploadStatusCallback | None,
        controller: FileDownloadUploadController | AsyncFileDownloadUploadController,
        ts: float,
    ):
        async with receive_stream:
            async for index, chunk in receive_stream:
                if controller.is_cancelled:
                    break

                chunk_enc = await self._runner.run_sync(encrypt_content, chunk, metadata.key)
                chunk_enc_hash = await self._runner.run_sync(hash_data, chunk_enc)

                data = FileUploadChunkRequestData(
                    uuid=file_uuid,
                    index=index,
                    parent=parent,
                    upload_key=upload_key,
                    hash=chunk_enc_hash,
                    chunk=chunk_enc,
                )
                result = (await self._api.v3.file.upload.chunk(data)).data

                async with upload_info_lock:
                    upload_info['chunk_count'] += 1
                    upload_info['byte_count'] += len(chunk)
                    upload_info['bucket'] = result.bucket
                    upload_info['region'] = result.region

                    await self._on_status(
                        status_callback,
                        file_uuid=file_uuid,
                        metadata=metadata,
                        controller=controller,
                        state=DownloadUploadState.in_progress,
                        num_chunks=num_chunks,
                        chunk_count=upload_info['chunk_count'],
                        byte_count=upload_info['byte_count'],
                    )

                    if logger.isEnabledFor(logging.DEBUG) and upload_info['chunk_count'] % DEBUG_PRINT_INTERVAL == 0:
                        took = time.monotonic() - ts
                        logger.debug(
                            'Upload file %r <%s>: %.1f%%, %d/%d chunks, %s, %s/s (%s:%s)',
                            metadata.name,
                            file_uuid,
                            upload_info['chunk_count'] / num_chunks * 100,
                            upload_info['chunk_count'],
                            num_chunks,
                            naturalsize(upload_info['byte_count'], binary=True),
                            naturalsize(upload_info['byte_count'] / took, binary=True),
                            upload_info['bucket'],
                            upload_info['region'],
                        )

    @staticmethod
    async def _on_status(
        callback: AsyncUploadStatusCallback | None,
        file_uuid: UUID,
        metadata: FileMetadata,
        controller: AsyncFileDownloadUploadController,
        state: DownloadUploadState,
        num_chunks: int,
        chunk_count: int = 0,
        byte_count: int = 0,
        error: ExceptionGroup | None = None,
    ) -> None:
        if not callback:
            return
        try:
            status = UploadStatus(
                uuid=file_uuid,
                metadata=metadata,
                controller=controller,
                state=state,
                num_chunks=num_chunks,
                chunk_count=chunk_count,
                byte_count=byte_count,
                error=error,
            )

            if asyncio.iscoroutinefunction(callback):
                await callback(status)
            else:
                await anyio.to_thread.run_sync(callback, status)
        except Exception as e:
            logger.exception('An error occurred in upload status callback: %s', e)

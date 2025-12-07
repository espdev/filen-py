from typing import Type
from dataclasses import dataclass, field
from enum import StrEnum, auto
import threading
import time

import anyio

from filen.errors import DownloadCancelled, UploadCancelled


class DownloadUploadState(StrEnum):
    """All states for downloading/uploading file process"""

    queued = auto()
    started = auto()
    in_progress = auto()
    paused = auto()
    cancelled = auto()
    failed = auto()
    done = auto()


class FileDownloadUploadController:
    """Control sync downloading/uploading file process"""

    def __init__(self, autostart: bool = True):
        self._start_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_cancelled = False
        self._is_paused = False
        self._autostart = autostart

        if autostart:
            self._start_event.set()
        self._pause_event.set()

    @property
    def is_cancelled(self) -> bool:
        """Return True if the downloading/uploading process was cancelled"""
        return self._is_cancelled

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start(self):
        """Start/resume downloading/uploading process"""
        self._start_event.set()
        self._pause_event.set()
        self._is_paused = False

    def pause(self):
        """Pause downloading/uploading process"""
        self._is_paused = True
        self._pause_event.clear()

    def cancel(self):
        """Cancel downloading/uploading process (interrupt downloading)"""
        self._is_cancelled = True
        self.start()

    def reset(self):
        """Reset the controller state"""
        self._start_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_cancelled = False
        self._is_paused = False

        if self._autostart:
            self._start_event.set()
        self._pause_event.set()

    def wait_for_start(self):
        """Wait for start (called in the downloader/uploader)"""
        self._start_event.wait()

    def wait_for_resume(self):
        """Wait for resume after pause (called in the downloader/uploader)"""
        self._pause_event.wait()

    def raise_for_cancellation(self, exc_type: Type[DownloadCancelled | UploadCancelled]):
        """Raise DownloadCancelled/UploadCancelled if the downloading/uploading process was cancelled"""
        if self._is_cancelled:
            raise exc_type('Cancelled by controller')


class AsyncFileDownloadUploadController:
    """Control async downloading/uploading file process"""

    def __init__(self, autostart: bool = True):
        self._start_event = anyio.Event()
        self._pause_event = anyio.Event()
        self._is_cancelled = False
        self._is_paused = False
        self._autostart = autostart

        if autostart:
            self._start_event.set()
        self._pause_event.set()

    @property
    def is_cancelled(self) -> bool:
        """Return True if the downloading/uploading process was cancelled"""
        return self._is_cancelled

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start(self):
        """Start/resume downloading/uploading process"""
        self._start_event.set()
        self._pause_event.set()
        self._is_paused = False

    def pause(self):
        """Pause downloading/uploading process"""
        if self._pause_event.is_set():
            self._is_paused = True
            self._pause_event = anyio.Event()

    def cancel(self):
        """Cancel downloading/uploading process (interrupt downloading/uploading)"""
        self._is_cancelled = True
        self.start()

    def reset(self):
        """Reset the controller state"""
        self._start_event = anyio.Event()
        self._pause_event = anyio.Event()
        self._is_cancelled = False
        self._is_paused = False

        if self._autostart:
            self._start_event.set()
        self._pause_event.set()

    async def wait_for_start(self):
        """Wait for start

        Called in the downloader/uploader
        """
        await self._start_event.wait()

    async def wait_for_resume(self):
        """Wait for resume after pause

        Called in the downloader/uploader
        """
        await self._pause_event.wait()

    def raise_for_cancellation(
        self,
        exc_type_or_cancel_scope: Type[DownloadCancelled | UploadCancelled] | anyio.CancelScope,
    ):
        """Raise DownloadCancelled/UploadCancell or call cancel_scope if the downloading/uploading process was cancelled

        Called in the downloader/uploader
        """
        if self._is_cancelled:
            msg = 'Cancelled by controller'
            if isinstance(exc_type_or_cancel_scope, anyio.CancelScope):
                exc_type_or_cancel_scope.cancel(msg)
            else:
                raise exc_type_or_cancel_scope(msg)


@dataclass(slots=True, frozen=True, kw_only=True)
class DownloadUploadStatusBase:
    controller: FileDownloadUploadController | AsyncFileDownloadUploadController
    state: DownloadUploadState
    num_chunks: int
    chunk_count: int
    byte_count: int
    error: ExceptionGroup | None
    timestamp: int = field(default_factory=time.time)

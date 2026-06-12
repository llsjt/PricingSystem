"""Cooperative cancellation state for graceful worker shutdown."""

from __future__ import annotations

import threading


class TaskCancelledError(RuntimeError):
    """Raised when shutdown requests the current task to stop cooperatively."""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def set(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    def is_set(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_set():
            raise TaskCancelledError("worker shutdown requested")


GLOBAL_CANCELLATION_TOKEN = CancellationToken()


def request_shutdown() -> None:
    GLOBAL_CANCELLATION_TOKEN.set()


def clear_shutdown() -> None:
    GLOBAL_CANCELLATION_TOKEN.clear()


def raise_if_cancelled() -> None:
    GLOBAL_CANCELLATION_TOKEN.raise_if_cancelled()


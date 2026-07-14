from __future__ import annotations

import itertools
import sys
import threading
from argparse import Namespace
from types import TracebackType
from typing import TextIO


TRANSFER_COMMAND_PREFIXES = ("Upload", "Download")


def is_transfer_command(command: str | None) -> bool:
    return bool(command and command.startswith(TRANSFER_COMMAND_PREFIXES))


class TransferProgress:
    """TTY-only progress indicator owned by the CLI presentation layer."""

    def __init__(
        self,
        label: str,
        *,
        enabled: bool,
        stream: TextIO = sys.stderr,
        interval_seconds: float = 0.1,
    ) -> None:
        self._label = label
        self._stream = stream
        self._interval_seconds = interval_seconds
        self._enabled = enabled and stream.isatty()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "TransferProgress":
        if not self._enabled:
            return self
        self._thread = threading.Thread(target=self._render, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self._enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._interval_seconds * 2, 0.2))
        self._stream.write("\r\033[2K")
        self._stream.flush()

    def _render(self) -> None:
        for frame in itertools.cycle("|/-\\"):
            if self._stop.wait(self._interval_seconds):
                break
            self._stream.write(f"\r{frame} {self._label}")
            self._stream.flush()


def transfer_progress_for(
    args: Namespace,
    *,
    stream: TextIO = sys.stderr,
) -> TransferProgress:
    command = getattr(args, "command", None)
    enabled = (
        is_transfer_command(command)
        and getattr(args, "output", "table") == "table"
        and getattr(args, "field", None) is None
    )
    return TransferProgress(
        f"{command} in progress. Press Ctrl-C to cancel.",
        enabled=enabled,
        stream=stream,
    )

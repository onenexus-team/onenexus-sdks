"""Opt-in standard-library logging integration; no global handler replacement."""

from __future__ import annotations

import atexit
import hashlib
import io
import json
import logging
import math
import os
import queue
import re
import sys
import threading
import time
import traceback
import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, TextIO

from .context import current_trace_id
from .drop_metric import _DROPS, DropReason
from .contract import (
    COMMON_FIELDS,
    MAX_DROPPED_FIELD_COUNT,
    MAX_ERROR_TYPE_CHARS,
    MAX_FIELD_BYTES,
    MAX_MESSAGE_BYTES,
    MAX_RECORD_BYTES,
    MAX_STACKTRACE_BYTES,
    ContractViolation,
    encode_record,
    validate_record,
)
from .request import REQUEST_FIELDS, current_request_fields

ERROR_TYPE_FIELD = "error.type"
STACKTRACE_FIELD = "exception.stacktrace"
TRUNCATED_FIELD = "logging.truncated"
DROPPED_FIELD = "logging.dropped_field_count"
ERROR_FINGERPRINT_FIELD = "logging.error_fingerprint"
_FRAME_LINE = re.compile(r":[0-9]+\)$")
TRUNCATION_MARK = "\u2026"
ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


@dataclass(frozen=True)
class LogConfig:
    service: str
    environment: str
    region: str
    allowed_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        errors = validate_record(
            {
                "timestamp": 0,
                "level": "INFO",
                "message": "Configuration check",
                "service": self.service,
                "environment": self.environment,
                "region": self.region,
            }
        )
        if errors:
            raise ContractViolation(errors)
        if not isinstance(self.allowed_fields, frozenset) or len(self.allowed_fields) > 32:
            raise ValueError("invalid_allowed_fields")
        if any(
            not isinstance(k, str) or not k or len(k) > 128 or k in COMMON_FIELDS
            for k in self.allowed_fields
        ):
            raise ValueError("invalid_allowed_fields")


def shorten(text: str, limit: int) -> tuple[str, bool]:
    """Cut at a character boundary so the text plus the mark fits ``limit`` UTF-8 bytes."""
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text, False
    budget = limit - len(TRUNCATION_MARK.encode("utf-8"))
    return data[:budget].decode("utf-8", "ignore") + TRUNCATION_MARK, True


def _encoded_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def _valid_error_type(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_ERROR_TYPE_CHARS and not any(c.isspace() for c in value)


def _field_value(key: str, value: object) -> tuple[object, bool] | None:
    """The value to emit and whether it was cut; None when it cannot be emitted."""
    if key == ERROR_TYPE_FIELD and not _valid_error_type(value):
        return None
    if key == STACKTRACE_FIELD and not (isinstance(value, str) and value):
        return None
    if isinstance(value, str):
        try:
            return shorten(value, MAX_STACKTRACE_BYTES if key == STACKTRACE_FIELD else MAX_FIELD_BYTES)
        except UnicodeError:
            return None  # Not valid Unicode (e.g. a lone surrogate): cannot be encoded.
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        _encoded_size(value)
    except (TypeError, ValueError, RecursionError):
        return None
    return value, False


def _frames(lines: list[str]) -> tuple[str, bool]:
    """Keep whole frames, innermost first, within the stack budget."""
    kept: list[str] = []
    size = 0
    for line in lines:
        line, cut = shorten(line, MAX_STACKTRACE_BYTES)
        cost = len(line.encode("utf-8")) + (1 if kept else 0)
        if cut or size + cost > MAX_STACKTRACE_BYTES:
            return "\n".join(kept) if kept else line, True
        kept.append(line)
        size += cost
    return "\n".join(kept), False


def error_fields(exc_info: ExcInfo) -> tuple[dict[str, str], bool]:
    """Type and frames of an exception; never its message or argument values."""
    error_type, _, tb = exc_info
    name = error_type.__qualname__
    if error_type.__module__ != "builtins":
        name = f"{error_type.__module__}.{name}"
    if not _valid_error_type(name):
        name = error_type.__name__[:MAX_ERROR_TYPE_CHARS]
    fields = {ERROR_TYPE_FIELD: name}
    lines = [
        f"at {frame.name} ({os.path.basename(frame.filename)}:{frame.lineno or 0})"
        for frame in reversed(traceback.extract_tb(tb))
    ]
    if not lines:
        return fields, False
    stack, cut = _frames(lines)
    fields[STACKTRACE_FIELD] = stack
    return fields, cut


def error_fingerprint(error_type: str, stacktrace: str | None = None) -> str:
    """Groups one failure across lines and builds (tests/logging error_fingerprint).

    The type and each frame without its line number; never the message.
    """
    frames = stacktrace.split("\n") if stacktrace else []
    text = error_type + "".join("\n" + _FRAME_LINE.sub(")", frame) for frame in frames)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _shrink_stack(record: dict[str, Any]) -> bool:
    """Drop the outermost frame; remove the stack once one frame is left."""
    stack = record.get(STACKTRACE_FIELD)
    if not isinstance(stack, str):
        return False
    head, sep, _ = stack.rpartition("\n")
    if sep:
        record[STACKTRACE_FIELD] = head
    else:
        del record[STACKTRACE_FIELD]
    return True


def _fit(record: dict[str, Any], removable: set[str], dropped: int, truncated: bool) -> None:
    """Shorten the stack, then remove the largest custom fields, until the record fits."""

    def flagged() -> dict[str, Any]:
        if truncated:
            record[TRUNCATED_FIELD] = True
        if dropped:
            record[DROPPED_FIELD] = min(dropped, MAX_DROPPED_FIELD_COUNT)
        return record

    while _encoded_size(flagged()) > MAX_RECORD_BYTES:
        if _shrink_stack(record):
            truncated = True
            continue
        candidates = [k for k in removable if k in record]
        if not candidates:
            return  # Validation reports record_too_large; the record is dropped.
        largest = max(candidates, key=lambda k: (_encoded_size({k: record[k]}), k))
        del record[largest]
        dropped += 1


def build_record(
    config: LogConfig,
    message: str,
    *,
    level: str = "INFO",
    event: str | None = None,
    outcome: str | None = None,
    fields: Mapping[str, Any] | None = None,
    exc_info: ExcInfo | None = None,
) -> dict[str, Any]:
    """Build and validate; errors never include the source record or message.

    A too-long message or string field is shortened and an unknown or
    unserialisable field is removed, so the line still arrives; the record says so
    in ``logging.truncated`` and ``logging.dropped_field_count``.
    """
    truncated = False
    dropped = 0
    if isinstance(message, str):
        message, truncated = shorten(message, MAX_MESSAGE_BYTES)
    record: dict[str, Any] = {
        "timestamp": time.time_ns(),
        "level": level,
        "message": message,
        "service": config.service,
        "environment": config.environment,
        "region": config.region,
    }
    if trace_id := current_trace_id():
        record["trace_id"] = trace_id
    if event is not None or outcome is not None:
        record.update(event=event, outcome=outcome)
    custom: set[str] = set()
    if fields is not None:
        if not isinstance(fields, Mapping):
            raise ContractViolation(["unapproved_custom_field"])
        allowed = config.allowed_fields | REQUEST_FIELDS
        for key, value in fields.items():
            emitted = _field_value(key, value) if key in allowed else None
            if emitted is None:
                dropped += 1
                continue
            record[key], cut = emitted
            truncated = truncated or cut
            if key not in REQUEST_FIELDS:
                custom.add(key)
    record.update(current_request_fields())
    if exc_info is not None:
        error, cut = error_fields(exc_info)
        for key, value in error.items():
            if key not in record:  # A caller-supplied value wins.
                record[key] = value
                # Only the SDK's stack can be cut; a caller stack keeps its own flag.
                truncated = truncated or (cut and key == STACKTRACE_FIELD)
    if isinstance(error_type := record.get(ERROR_TYPE_FIELD), str):
        # Before fitting: a shortened stack keeps the fingerprint.
        record[ERROR_FINGERPRINT_FIELD] = error_fingerprint(error_type, record.get(STACKTRACE_FIELD))
    _fit(record, custom, dropped, truncated)
    if "request_event" in record:
        profile = "request"
    elif event is not None or outcome is not None:
        profile = "lifecycle"
    else:
        profile = "correlated" if "trace_id" in record else "common"
    errors = validate_record(record, profile)
    if errors:
        raise ContractViolation(errors)
    return record


# One write model in every language (design review F2; tests/logging write_model).
QUEUE_CAPACITY = 1024
CLOSE_TIMEOUT_SECONDS = 2.0
# An ERROR/FATAL line waits this long for the writer, so the line logged just
# before a hard exit (os._exit, a crash) is not lost. Bounded: the caller budget.
ERROR_WAIT_SECONDS = 0.05
_STOP = object()
_WRITERS: weakref.WeakSet[_Writer] = weakref.WeakSet()


class _Writer:
    """A bounded queue and one daemon thread that owns all writes to one stream.

    The caller never waits on the output (an ERROR/FATAL line waits at most
    ``ERROR_WAIT_SECONDS``): a full queue drops the line and counts it. A failed
    write is counted and the writer goes on with the next line; a line cut short
    by a failure is ended with a newline first, so the next line stays valid JSON.

    The thread starts with the first line, so a handler that never logs owns no
    thread. A stream backed by a file descriptor (stdout, a pipe, a file) is
    written with ``os.write``: no Python buffer lock is held, so a writer still
    blocked when the interpreter exits cannot abort the process. Other streams
    use ``write``.

    After ``os.fork`` the child gets a new lock, queue, thread and counters: the
    parent's may be held by a thread that does not exist in the child. At exit
    every writer is drained (one shared deadline) and stopped, even when its
    handler was already collected.

    Every drop is also added to the process-wide counter for ``service``
    (design review R1), at the same site as the writer's own counter.
    """

    def __init__(self, stream: TextIO, capacity: int, service: str) -> None:
        if capacity < 1:
            raise ValueError("queue_capacity_must_be_positive")
        self.service = service
        _DROPS.register(service)
        self.stream = stream
        self.capacity = capacity
        self._fd = _file_descriptor(stream)
        self._closed = False
        self._reset()
        _WRITERS.add(self)

    def _reset(self) -> None:
        self.written = self.queue_full = self.io_errors = self.closed_drops = self.invalid = 0
        self._accepted = self._done = 0
        self._lock = threading.Lock()
        self._progress = threading.Condition(threading.Lock())
        self._queue: queue.Queue[object] = queue.Queue(self.capacity)
        self._broken_line = False
        self._thread: threading.Thread | None = None

    @property
    def pending(self) -> int:
        """Lines accepted but not yet written or failed."""
        return self._accepted - self._done

    def count_invalid(self) -> None:
        with self._lock:
            self.invalid += 1
        _DROPS.add(self.service, DropReason.INVALID)

    def submit(self, line: str) -> int | None:
        """Queue the line; its ticket, or None when it was dropped and counted."""
        with self._lock:
            if self._closed:
                self.closed_drops += 1
                _DROPS.add(self.service, DropReason.CLOSED)
                return None
            try:
                self._queue.put_nowait(line)
            except queue.Full:
                self.queue_full += 1
                _DROPS.add(self.service, DropReason.QUEUE_FULL)
                return None
            with self._progress:
                self._accepted += 1
                ticket = self._accepted
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="onenexus-log-writer", daemon=True)
                self._thread.start()
            return ticket

    def wait_written(self, ticket: int, timeout: float) -> None:
        if threading.current_thread() is self._thread:
            return  # logging from the writer thread itself
        with self._progress:
            self._progress.wait_for(lambda: self._done >= ticket, timeout)

    def _run(self) -> None:
        jobs = self._queue  # this thread's own queue, even after a fork resets self._queue
        while True:
            line = jobs.get()
            if line is _STOP:
                return
            self._write(str(line))
            with self._progress:
                self._done += 1
                self._progress.notify_all()

    def _write(self, line: str) -> None:
        fd, stream = self._fd, self.stream  # setStream may swap them while we write
        if fd is None:
            try:
                if self._broken_line:
                    stream.write("\n")
                    self._broken_line = False
                stream.write(line)
            except BlockingIOError as error:
                self._count_io_error()
                self._broken_line = error.characters_written > 0
                return
            except Exception:
                self._count_io_error()
                return
            self.written += 1
            try:
                stream.flush()
            except Exception:
                pass  # the line is in the stream's buffer; the next flush retries
            return
        prefix = 1 if self._broken_line else 0
        data = (b"\n" if prefix else b"") + line.encode("utf-8")
        sent = 0
        try:
            while sent < len(data):  # os.write may write part of the line
                sent += os.write(fd, data[sent:])
            self._broken_line = False
            self.written += 1
        except Exception:
            self._count_io_error()
            # Still cut: part of this line went out, or the earlier cut line was not ended.
            self._broken_line = sent > prefix or (prefix == 1 and sent == 0)

    def _count_io_error(self) -> None:
        # Only the writer thread changes io_errors; the process counter has its own lock.
        self.io_errors += 1
        _DROPS.add(self.service, DropReason.IO_ERRORS)

    def drain(self, timeout: float) -> bool:
        """Wait until every accepted line is written or failed, or until ``timeout``."""
        if threading.current_thread() is self._thread:
            return not self.pending
        with self._progress:
            return self._progress.wait_for(lambda: self._done >= self._accepted, timeout)

    def close(self, timeout: float) -> bool:
        with self._lock:
            already = self._closed
            self._closed = True
            thread = self._thread
        if already or thread is None:
            return not self.pending
        if threading.current_thread() is thread:
            self._queue_stop()  # close from inside a write: never wait on ourselves
            return not self.pending
        deadline = time.monotonic() + timeout
        drained = self.drain(timeout)
        if self._queue_stop():
            thread.join(max(0.0, deadline - time.monotonic()))
        return drained

    def _queue_stop(self) -> bool:
        try:
            self._queue.put_nowait(_STOP)
        except queue.Full:
            return False  # daemon thread; undelivered lines stay pending
        return True

    def after_fork_in_child(self) -> None:
        if not self._closed:
            self._reset()


def _file_descriptor(stream: TextIO) -> int | None:
    """The stream's descriptor after flushing its buffer, or None (e.g. StringIO)."""
    try:
        fd = stream.fileno()
        stream.flush()
    except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
        return None
    return fd


def _close_all_writers() -> None:
    # One deadline for the whole process, however many handlers exist.
    deadline = time.monotonic() + CLOSE_TIMEOUT_SECONDS
    for writer in list(_WRITERS):
        writer.close(max(0.0, deadline - time.monotonic()))


atexit.register(_close_all_writers)


def _after_fork_in_child() -> None:
    _DROPS.after_fork_in_child()
    for writer in list(_WRITERS):
        writer.after_fork_in_child()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork_in_child)


class JsonLogHandler(logging.StreamHandler[TextIO]):
    """Contract-backed handler whose caller never waits on the output.

    Records are built and validated on the caller's thread, then queued for one
    background writer (``QUEUE_CAPACITY`` lines). A full queue, a rejected record,
    a failed write and a write after close are each counted, never raised and
    never passed to logging's handleError (which may print the original record).
    ``flush`` and ``close`` wait up to ``CLOSE_TIMEOUT_SECONDS`` for queued lines;
    an ERROR/FATAL line waits up to ``ERROR_WAIT_SECONDS`` so it survives a hard
    exit. Output can trail the call: read it after ``flush`` or ``close``. Lines
    written through ``print`` and through this handler may interleave out of order.
    An exception adds its type and frames (``error.type``,
    ``exception.stacktrace``), never its text. Other handlers are not modified.
    """

    def __init__(
        self,
        config: LogConfig,
        stream: TextIO | None = None,
        *,
        queue_capacity: int = QUEUE_CAPACITY,
    ) -> None:
        super().__init__(stream if stream is not None else sys.stdout)
        self.config = config
        self._writer = _Writer(self.stream, queue_capacity, config.service)

    @property
    def dropped_records(self) -> int:
        """Every line that was not written: invalid, queue full, write error, closed."""
        w = self._writer
        return w.invalid + w.queue_full + w.io_errors + w.closed_drops

    def stats(self) -> dict[str, int]:
        """The shared counters (tests/logging write_model)."""
        w = self._writer
        return {
            "written": w.written,
            "invalid": w.invalid,
            "queue_full": w.queue_full,
            "io_errors": w.io_errors,
            "closed": w.closed_drops,
            "pending": w.pending,
        }

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = (
                "FATAL"
                if record.levelno >= logging.CRITICAL
                else "ERROR"
                if record.levelno >= logging.ERROR
                else "WARN"
                if record.levelno >= logging.WARNING
                else "INFO"
                if record.levelno >= logging.INFO
                else "DEBUG"
                if record.levelno >= logging.DEBUG
                else "TRACE"
            )
            value = build_record(
                self.config,
                record.getMessage(),
                level=level,
                event=getattr(record, "event", None),
                outcome=getattr(record, "outcome", None),
                fields=getattr(record, "fields", None),
                exc_info=record.exc_info if record.exc_info and record.exc_info[0] else None,
            )
            line = encode_record(value) + "\n"
        except Exception:
            # Logging must not change business outcomes or echo rejected payloads.
            self._writer.count_invalid()
            return
        ticket = self._writer.submit(line)
        if ticket is not None and record.levelno >= logging.ERROR:
            self._writer.wait_written(ticket, ERROR_WAIT_SECONDS)

    def flush(self) -> None:
        """Wait (bounded) until queued lines are written; at once after close."""
        if self._writer._closed:
            return
        self._writer.drain(CLOSE_TIMEOUT_SECONDS)

    def close_within(self, timeout: float = CLOSE_TIMEOUT_SECONDS) -> bool:
        """Stop accepting lines; drain until ``timeout``. True when nothing was lost."""
        drained = self._writer.close(timeout)
        super().close()
        return drained

    def close(self) -> None:
        """logging's close: drain up to ``CLOSE_TIMEOUT_SECONDS``, then stop."""
        self.close_within()

    def setStream(self, stream: TextIO) -> TextIO | None:
        self.flush()
        previous = super().setStream(stream)
        self._writer.stream = self.stream
        self._writer._fd = _file_descriptor(self.stream)
        return previous


_INSTALL_LOCK = threading.Lock()


def install_handler(
    logger: logging.Logger,
    config: LogConfig,
    *,
    stream: TextIO | None = None,
) -> JsonLogHandler:
    """Install once per logger; configuration conflicts fail at startup.

    Does not change logger levels, propagation, other handlers or OTel providers.
    Caller owns removal/close. Avoid installing on both parent and child loggers.
    """
    target = stream if stream is not None else sys.stdout
    with _INSTALL_LOCK:
        for handler in logger.handlers:
            if isinstance(handler, JsonLogHandler):
                if handler.config != config or handler.stream is not target:
                    raise ValueError("logging_configuration_conflict")
                return handler
        handler = JsonLogHandler(config, target)
        logger.addHandler(handler)
        return handler

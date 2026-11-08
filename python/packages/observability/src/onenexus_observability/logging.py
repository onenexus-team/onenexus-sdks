"""Opt-in standard-library logging integration; no global handler replacement."""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import threading
import time
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, TextIO

from .context import current_trace_id
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


class JsonLogHandler(logging.StreamHandler[TextIO]):
    """Direct bounded-output handler. Stream writes may block; no queue or retries.

    Failed/invalid emissions increment dropped_records and never call logging's
    handleError (which may print the original record). An exception adds its type
    and frames (``error.type``, ``exception.stacktrace``), never its text.
    The application's existing OTLP handler is not modified.
    """

    def __init__(self, config: LogConfig, stream: TextIO | None = None) -> None:
        super().__init__(stream if stream is not None else sys.stdout)
        self.config = config
        self.dropped_records = 0

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
            self.stream.write(encode_record(value) + "\n")
            self.flush()
        except Exception:
            # Logging must not change business outcomes or echo rejected payloads.
            self.dropped_records += 1


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

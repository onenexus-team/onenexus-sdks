"""Opt-in standard-library logging integration; no global handler replacement."""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TextIO

from .context import current_trace_id
from .contract import COMMON_FIELDS, ContractViolation, encode_record, validate_record


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


def build_record(
    config: LogConfig,
    message: str,
    *,
    level: str = "INFO",
    event: str | None = None,
    outcome: str | None = None,
    fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate; errors never include the source record or message."""
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
    if fields is not None:
        if not isinstance(fields, Mapping) or any(k not in config.allowed_fields for k in fields):
            raise ContractViolation(["unapproved_custom_field"])
        record.update(fields)
    profile = (
        "lifecycle"
        if event is not None or outcome is not None
        else ("correlated" if "trace_id" in record else "common")
    )
    errors = validate_record(record, profile)
    if errors:
        raise ContractViolation(errors)
    return record


class JsonLogHandler(logging.StreamHandler[TextIO]):
    """Direct bounded-output handler. Stream writes may block; no queue or retries.

    Failed/invalid emissions increment dropped_records and never call logging's
    handleError (which may print the original record). No exception text is added.
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

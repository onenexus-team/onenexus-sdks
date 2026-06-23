"""HTTP transport, typed errors, and the request protocol."""

from __future__ import annotations

from .errors import (
    AlreadyExistsError,
    FailedPreconditionError,
    ForbiddenError,
    InternalError,
    InvalidArgumentError,
    NotFoundError,
    PlatformError,
    ResourceExhaustedError,
    UnauthenticatedError,
    UnavailableError,
    parse_platform_error,
)
from .transport import RETRYABLE_STATUS, RetryConfig, Transport, send_authorized

__all__ = [
    "RETRYABLE_STATUS",
    "AlreadyExistsError",
    "FailedPreconditionError",
    "ForbiddenError",
    "InternalError",
    "InvalidArgumentError",
    "NotFoundError",
    "PlatformError",
    "ResourceExhaustedError",
    "RetryConfig",
    "Transport",
    "UnauthenticatedError",
    "UnavailableError",
    "parse_platform_error",
    "send_authorized",
]

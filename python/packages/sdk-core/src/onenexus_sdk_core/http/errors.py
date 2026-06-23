"""Typed error hierarchy mapped from RFC 9457 Problem Details responses.

Mirrors the ``PlatformError`` family in ``@onenexus/sdk-core``. Each non-2xx
response from a platform API carries a ``application/problem+json`` body with a
machine-readable ``code``; :func:`parse_platform_error` maps that code (falling
back to the HTTP status) to the matching :class:`PlatformError` subclass.
"""

from __future__ import annotations

from typing import Any

import httpx


class PlatformError(Exception):
    """Base class for typed platform API errors."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str | None = None,
        detail: str | None = None,
        request_id: str | None = None,
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.detail = detail
        self.request_id = request_id
        self.field_errors = field_errors


class InvalidArgumentError(PlatformError):
    """The request was malformed or failed validation (HTTP 400)."""


class UnauthenticatedError(PlatformError):
    """The request lacked valid authentication (HTTP 401)."""


class ForbiddenError(PlatformError):
    """The caller is authenticated but not permitted (HTTP 403)."""


class NotFoundError(PlatformError):
    """The target resource does not exist (HTTP 404)."""


class AlreadyExistsError(PlatformError):
    """The resource already exists (HTTP 409)."""


class FailedPreconditionError(PlatformError):
    """A precondition for the operation was not met (HTTP 412/422)."""


class ResourceExhaustedError(PlatformError):
    """A quota or rate limit was exceeded (HTTP 429)."""


class UnavailableError(PlatformError):
    """The service is temporarily unavailable (HTTP 503)."""


class InternalError(PlatformError):
    """The service encountered an unexpected condition (HTTP 5xx)."""


_CODE_MAP: dict[str, type[PlatformError]] = {
    "invalid_argument": InvalidArgumentError,
    "unauthenticated": UnauthenticatedError,
    "permission_denied": ForbiddenError,
    "forbidden": ForbiddenError,
    "not_found": NotFoundError,
    "already_exists": AlreadyExistsError,
    "failed_precondition": FailedPreconditionError,
    "resource_exhausted": ResourceExhaustedError,
    "unavailable": UnavailableError,
    "internal": InternalError,
}

_STATUS_MAP: dict[int, type[PlatformError]] = {
    400: InvalidArgumentError,
    401: UnauthenticatedError,
    403: ForbiddenError,
    404: NotFoundError,
    409: AlreadyExistsError,
    412: FailedPreconditionError,
    422: FailedPreconditionError,
    429: ResourceExhaustedError,
    503: UnavailableError,
}


def parse_platform_error(response: httpx.Response) -> PlatformError:
    """Build the typed :class:`PlatformError` for a non-2xx ``response``."""
    body = _read_problem_body(response)
    status = response.status_code
    code = _opt_str(body.get("code"))
    detail = _opt_str(body.get("detail"))
    request_id = _opt_str(body.get("requestId"))
    title = _opt_str(body.get("title"))

    error_cls = _CODE_MAP.get(code or "") or _STATUS_MAP.get(status)
    if error_cls is None:
        error_cls = InternalError if status >= 500 else PlatformError

    field_errors = _read_field_errors(body)
    message = detail or title or f"platform request failed with status {status}"
    return error_cls(
        message,
        status=status,
        code=code,
        detail=detail,
        request_id=request_id,
        field_errors=field_errors,
    )


def _read_problem_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _read_field_errors(body: dict[str, Any]) -> dict[str, list[str]] | None:
    errors = body.get("errors")
    if not isinstance(errors, dict):
        return None
    result: dict[str, list[str]] = {}
    for key, value in errors.items():
        if isinstance(value, list):
            result[str(key)] = [str(item) for item in value]
    return result or None


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


__all__ = [
    "AlreadyExistsError",
    "FailedPreconditionError",
    "ForbiddenError",
    "InternalError",
    "InvalidArgumentError",
    "NotFoundError",
    "PlatformError",
    "ResourceExhaustedError",
    "UnauthenticatedError",
    "UnavailableError",
    "parse_platform_error",
]

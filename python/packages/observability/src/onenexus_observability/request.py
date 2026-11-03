"""Request log context. Authentication and response observation belong to the caller."""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
from threading import RLock
from typing import Any

REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "principal_id",
        "tenant_id",
        "error_code",
        "request_event",
        "http.request.method",
        "http.route",
        "http.response.status_code",
        "duration_ms",
    }
)
_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_TENANT = re.compile(r"[0-9a-f]{32}")
_PRINCIPAL = re.compile(
    r"nx1://[A-Za-z0-9._:-]+/([0-9a-f]{32})/[A-Za-z0-9._:-]+/[A-Za-z0-9._:-]+/(User|ServiceClient|Workload)/[A-Za-z0-9._:-]+"
)
_current: ContextVar[RequestLogContext | None] = ContextVar("request_log_context", default=None)


class RequestLogContext:
    """Mutable, request-local attribution; never use this object as authorization."""

    def __init__(self, request_id: str) -> None:
        if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
            raise ValueError("invalid_request_id")
        self._lock = RLock()
        self._closed = False
        self._fields: dict[str, Any] = {
            "request_id": request_id,
            "principal_id": None,
            "tenant_id": None,
        }

    def bind_verified_identity(self, principal_id: str | None, tenant_id: str | None) -> None:
        """Call only after credential verification, before policy/quota decisions.

        Tenant IDs use canonical lowercase UUID-N form. Legacy keys may have a
        verified tenant but no canonical owner. Invalid attribution fails closed.
        """
        tenant = (
            tenant_id
            if isinstance(tenant_id, str) and _TENANT.fullmatch(tenant_id) and tenant_id != "0" * 32
            else None
        )
        match = (
            _PRINCIPAL.fullmatch(principal_id)
            if isinstance(principal_id, str) and len(principal_id) <= 1024
            else None
        )
        principal = principal_id if match and tenant and match[1] == tenant else None
        with self._lock:
            if not self._closed:
                self._fields.update(principal_id=principal, tenant_id=tenant)

    def set_error(self, code: str) -> None:
        if not isinstance(code, str) or not _ID.fullmatch(code):
            raise ValueError("invalid_error_code")
        with self._lock:
            if not self._closed:
                self._fields["error_code"] = code

    def fields(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._fields)

    def terminal_fields(
        self,
        method: str,
        route: str,
        status_code: int | None,
        duration_ms: float,
        *,
        interrupted: bool = False,
    ) -> dict[str, Any]:
        """Use the route template and actual observed status, including streaming 200."""
        fields = self.fields()
        if not fields:
            raise ValueError("request_context_closed")
        fields.update(
            {
                "request_event": "interrupted" if interrupted else "completed",
                "http.request.method": method,
                "http.route": route,
                "http.response.status_code": status_code,
                "duration_ms": duration_ms,
                "error_code": fields.get("error_code")
                or (
                    "UNCLASSIFIED" if isinstance(status_code, int) and status_code >= 400 else None
                ),
            }
        )
        return fields

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._fields.clear()


@contextmanager
def request_log_context(request_id: str) -> Iterator[RequestLogContext]:
    """Clear shared state at exit, including references inherited by child tasks."""
    receipt = RequestLogContext(request_id)
    token = _current.set(receipt)
    try:
        yield receipt
    finally:
        receipt.close()
        _current.reset(token)


def current_request_fields() -> dict[str, Any]:
    receipt = _current.get()
    return receipt.fields() if receipt else {}

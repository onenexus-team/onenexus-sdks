"""Base class for generated OneNexus service clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta
from types import TracebackType
from typing import Any

import httpx

from .credentials.model import ClientContext, Credentials, default_client_context
from .http.transport import RetryConfig, send_authorized


class ClientBase:
    """Owns the credential context and async HTTP transport for a service client.

    Concrete clients (generated or hand-written) subclass this and bind generated
    operation functions to :meth:`request`. Construction is cheap and performs no
    network I/O.

    Satisfies the :class:`onenexus_sdk_core.http.Transport` protocol, so generated
    operations accept an instance as their transport argument.
    """

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        context: ClientContext | None = None,
        refresh_leeway: timedelta | None = None,
        retry: RetryConfig | None = None,
        timeout: float = 30.0,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._credentials = credentials
        ctx = context if context is not None else default_client_context()
        if refresh_leeway is not None:
            ctx = replace(ctx, refresh_leeway=refresh_leeway)
        self._context = ctx
        self._retry = retry if retry is not None else RetryConfig()
        self._owns_http = http is None
        self._http = (
            http
            if http is not None
            else httpx.AsyncClient(base_url=base_url, timeout=timeout)
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Send an authorized request through the platform transport."""
        return await send_authorized(
            self._http,
            self._credentials,
            self._context,
            self._retry,
            method=method,
            url=path,
            json=json,
            params=params,
            headers=headers,
        )

    async def aclose(self) -> None:
        """Close the owned HTTP client, if this instance created it."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> ClientBase:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()


__all__ = ["ClientBase"]

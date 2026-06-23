"""Async HTTP transport with credential injection, retry, and clock observation."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Protocol, runtime_checkable

import httpx

from ..credentials.model import ClientContext, Clock, Credentials
from .errors import parse_platform_error

#: HTTP statuses the transport retries. ``401`` is included so a token rejected
#: by the server (e.g. revoked, or rejected due to clock skew) triggers a fresh
#: resolve on the next attempt after the server ``Date`` corrects the clock.
RETRYABLE_STATUS = frozenset({401, 408, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Retry policy: exponential backoff with full jitter, capped per attempt."""

    limit: int = 2
    base_delay: timedelta = timedelta(milliseconds=300)
    backoff_limit: timedelta = timedelta(seconds=5)


@runtime_checkable
class Transport(Protocol):
    """The request surface generated client code depends on.

    :class:`onenexus_sdk_core.client.ClientBase` satisfies this protocol; the
    generated operation functions type their first argument against it so they
    never depend on a concrete client class.
    """

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        ...


async def send_authorized(
    http: httpx.AsyncClient,
    credentials: Credentials,
    context: ClientContext,
    retry: RetryConfig,
    *,
    method: str,
    url: str,
    json: Any = None,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    """Resolve credentials, send the request, and retry retryable failures.

    Credential errors raised by :meth:`Credentials.resolve` (``StaleCredentialsError``
    / ``AuthenticationError``) are not caught here; they propagate immediately so
    the caller fails fast rather than burning the retry budget.
    """
    attempt = 0
    while True:
        token = await credentials.resolve(context)
        request_headers = dict(headers or {})
        request_headers["Authorization"] = f"{token.token_type} {token.access_token}"

        response = await http.request(
            method,
            url,
            json=json,
            params=dict(params) if params is not None else None,
            headers=request_headers,
        )
        _observe_server_date(context.clock, response)

        if response.status_code < 400:
            return response
        if response.status_code in RETRYABLE_STATUS and attempt < retry.limit:
            attempt += 1
            await asyncio.sleep(_retry_delay(attempt, retry))
            continue
        raise parse_platform_error(response)


def _retry_delay(attempt: int, retry: RetryConfig) -> float:
    """Full-jitter exponential backoff in seconds, clamped to ``backoff_limit``."""
    base_seconds = retry.base_delay.total_seconds()
    exponential = base_seconds * (2 ** (attempt - 1))
    jittered = random.random() * exponential
    return float(min(retry.backoff_limit.total_seconds(), jittered))


def _observe_server_date(clock: Clock, response: httpx.Response) -> None:
    header = response.headers.get("date")
    if header is None:
        return
    try:
        server_date: datetime = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return
    clock.observe_server_time(server_date)


__all__ = ["RETRYABLE_STATUS", "RetryConfig", "Transport", "send_authorized"]

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

import httpx
from kiota_abstractions.api_error import APIError
from onenexus_cas_client import AssumeS3RoleRequest, AssumeS3RoleResponse, CasClient

from ..retry import RetryPolicy

S3RoleClientFactory = Callable[[], CasClient]
T = TypeVar("T")


def create_runtime_s3_credential(
    *,
    cas_client_factory: S3RoleClientFactory | None,
    role_name: str,
    endpoint_url: str,
    bucket: str,
    prefix: str,
    retry_policy: RetryPolicy | None = None,
) -> dict[str, Any]:
    if cas_client_factory is None:
        raise ValueError("CAS client factory is required for SDK-managed S3 transfers")

    response = _run_async(
        lambda: _assume_s3_role(
            cas_client_factory,
            role_name,
            retry_policy or RetryPolicy(),
        )
    )
    if (
        response.access_key_id is None
        or response.secret_access_key is None
        or response.session_token is None
    ):
        raise RuntimeError("CAS AssumeS3Role returned incomplete S3 credentials")

    return {
        "endpoint_url": endpoint_url,
        "bucket": bucket,
        "prefix": prefix,
        "access_key": response.access_key_id,
        "secret_key": response.secret_access_key,
        "session_token": response.session_token,
        "expires_at": response.expiration.isoformat()
        if response.expiration is not None
        else None,
    }


async def _assume_s3_role(
    cas_client_factory: S3RoleClientFactory,
    role_name: str,
    retry_policy: RetryPolicy,
) -> AssumeS3RoleResponse:
    attempt = 1
    started_at = time.monotonic()
    while True:
        delay: float | None = None
        client = cas_client_factory()
        try:
            return await client.assume_s3_role(AssumeS3RoleRequest(role_name=role_name))
        except Exception as error:
            if not _should_retry(error, retry_policy, attempt, started_at):
                raise
            delay = _retry_delay(error, retry_policy, attempt)
            if time.monotonic() - started_at + delay > (
                retry_policy.max_elapsed_seconds
            ):
                raise
        finally:
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()

        assert delay is not None
        await asyncio.sleep(delay)
        attempt += 1


def _should_retry(
    error: Exception,
    policy: RetryPolicy,
    attempt: int,
    started_at: float,
) -> bool:
    if not policy.enabled or attempt >= policy.max_attempts:
        return False
    if time.monotonic() - started_at >= policy.max_elapsed_seconds:
        return False
    if isinstance(error, (httpx.TransportError, TimeoutError, ConnectionError)):
        return True
    if isinstance(error, APIError):
        status = error.response_status_code
        return status in {408, 429} or (status is not None and status >= 500)
    return False


def _retry_delay(error: Exception, policy: RetryPolicy, attempt: int) -> float:
    retry_after = _retry_after(error)
    if retry_after is not None:
        return min(retry_after, policy.max_delay_seconds)
    ceiling = min(
        policy.base_delay_seconds * (2 ** (attempt - 1)),
        policy.max_delay_seconds,
    )
    return random.uniform(0, ceiling)


def _retry_after(error: Exception) -> float | None:
    if not isinstance(error, APIError) or not error.response_headers:
        return None
    value = next(
        (
            header_value
            for header_name, header_value in error.response_headers.items()
            if header_name.lower() == "retry-after"
        ),
        None,
    )
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max((retry_at - datetime.now(UTC)).total_seconds(), 0.0)


def _run_async(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    raise RuntimeError(
        "SDK-managed S3 transfer uses the sync onenexus client and cannot run "
        "inside an active asyncio event loop"
    )

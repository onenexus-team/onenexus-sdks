from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from onenexus_cas_client import AssumeS3RoleRequest, AssumeS3RoleResponse, CasClient

S3RoleClientFactory = Callable[[], CasClient]
T = TypeVar("T")


def create_runtime_s3_credential(
    *,
    cas_client_factory: S3RoleClientFactory | None,
    role_name: str,
    endpoint_url: str,
    bucket: str,
    prefix: str,
) -> dict[str, Any]:
    if cas_client_factory is None:
        raise ValueError(
            "CAS client factory is required for SDK-managed S3 transfers"
        )

    response = _run_async(lambda: _assume_s3_role(cas_client_factory, role_name))
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
) -> AssumeS3RoleResponse:
    client = cas_client_factory()
    try:
        return await client.assume_s3_role(AssumeS3RoleRequest(role_name=role_name))
    finally:
        close = getattr(client, "aclose", None)
        if close is not None:
            await close()


def _run_async(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    raise RuntimeError(
        "SDK-managed S3 transfer uses the sync onenexus client and cannot run "
        "inside an active asyncio event loop"
    )

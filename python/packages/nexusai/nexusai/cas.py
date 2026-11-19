from __future__ import annotations

from datetime import UTC, datetime

import httpx
from onenexus_cas_client import CasClient
from onenexus_sdk_core import (
    AccessToken,
    ClientContext,
    Credentials,
    TokenGrantCredentials,
)

from .config import CAS_BASE_URL


def _access_token_from_token(token: str) -> AccessToken:
    # MLOps gateway already authenticates bearer tokens. For CAS calls the SDK
    # should forward the token and let CAS decide validity, matching backend
    # runtime behavior. A synthetic short expiry would make opaque credentials
    # fail locally even while the upstream token is still valid.
    expires_at = datetime.max.replace(tzinfo=UTC)
    return AccessToken(access_token=token, expires_at=expires_at)


def credentials_from_token(token: str) -> TokenGrantCredentials:
    return TokenGrantCredentials(token=_access_token_from_token(token))


def create_cas_client(
    token: str,
    *,
    base_url: str = CAS_BASE_URL,
    context: ClientContext | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> CasClient:
    return create_cas_client_with_credentials(
        credentials_from_token(token),
        base_url=base_url,
        context=context,
        http_client=http_client,
    )


def create_cas_client_with_credentials(
    credentials: Credentials,
    *,
    base_url: str = CAS_BASE_URL,
    context: ClientContext | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> CasClient:
    return CasClient(
        base_url=base_url,
        credentials=credentials,
        context=context,
        http_client=http_client,
    )


__all__ = [
    "create_cas_client",
    "create_cas_client_with_credentials",
    "credentials_from_token",
]

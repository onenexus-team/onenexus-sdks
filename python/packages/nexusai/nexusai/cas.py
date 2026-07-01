from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .auth import token_expires_at
from .config import CAS_BASE_URL


def access_token_from_string(token: str):
    from onenexus_sdk_core import AccessToken

    expires_at = token_expires_at(token)
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(days=365)
    return AccessToken(access_token=token, expires_at=expires_at)


def credentials_from_access_token(token: str):
    from onenexus_sdk_core import TokenGrantCredentials

    return TokenGrantCredentials(token=access_token_from_string(token))


def create_cas_client(
    token: str,
    *,
    base_url: str = CAS_BASE_URL,
    context=None,
    http_client=None,
):
    from onenexus_cas_client import CasClient

    return CasClient(
        base_url=base_url,
        credentials=credentials_from_access_token(token),
        context=context,
        http_client=http_client,
    )


__all__ = [
    "access_token_from_string",
    "create_cas_client",
    "credentials_from_access_token",
]

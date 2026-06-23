"""Internal OIDC/OAuth helpers shared by the active credential implementations.

Not part of the public API.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt

from .errors import AuthenticationError
from .model import AccessToken, Clock

#: OAuth error codes that indicate the credential source itself was rejected.
_AUTH_FAILURE_ERRORS = frozenset(
    {"invalid_client", "invalid_grant", "unauthorized_client", "access_denied"}
)

#: Fallback access-token lifetime when the server omits ``expires_in``
#: (the OAuth 2.0 default per RFC 6749 §5.1).
_DEFAULT_EXPIRES_IN = timedelta(hours=1)

JWT_BEARER_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
CLIENT_ASSERTION_JWT_TYPE = "client-authentication+jwt"


@dataclass(frozen=True, slots=True)
class ServerMetadata:
    """The subset of an OIDC discovery document the SDK needs."""

    issuer: str
    token_endpoint: str

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> ServerMetadata:
        return cls(
            issuer=str(document["issuer"]),
            token_endpoint=str(document["token_endpoint"]),
        )


async def discover(http: httpx.AsyncClient, issuer: str) -> ServerMetadata:
    """Fetch and parse the OIDC discovery document for ``issuer``."""
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    response = await http.get(url)
    response.raise_for_status()
    return ServerMetadata.from_document(response.json())


def discover_sync(http: httpx.Client, issuer: str) -> ServerMetadata:
    """Fetch and parse the OIDC discovery document for ``issuer`` synchronously."""
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    response = http.get(url)
    response.raise_for_status()
    return ServerMetadata.from_document(response.json())


async def request_token(
    http: httpx.AsyncClient,
    token_endpoint: str,
    form: dict[str, str],
) -> dict[str, Any]:
    """POST a token request, mapping authentication rejections to errors.

    Raises:
        AuthenticationError: when the authority rejects the credential source
            (HTTP 401, or HTTP 400 with a terminal OAuth error code).
    """
    response = await http.post(
        token_endpoint,
        data=form,
        headers={"Accept": "application/json"},
    )
    if response.is_success:
        return _as_dict(response.json())

    error_code, error_description = _oauth_error(response)
    if response.status_code == 401 or (
        response.status_code == 400 and error_code in _AUTH_FAILURE_ERRORS
    ):
        detail = error_code or response.status_code
        if error_description:
            detail = f"{detail}: {error_description}"
        raise AuthenticationError(
            f"token request rejected by the authentication authority: {detail}"
        )
    response.raise_for_status()
    return _as_dict(response.json())


def request_token_sync(
    http: httpx.Client,
    token_endpoint: str,
    form: dict[str, str],
) -> dict[str, Any]:
    """POST a token request synchronously, mapping authentication rejections."""
    response = http.post(
        token_endpoint,
        data=form,
        headers={"Accept": "application/json"},
    )
    if response.is_success:
        return _as_dict(response.json())

    error_code, error_description = _oauth_error(response)
    if response.status_code == 401 or (
        response.status_code == 400 and error_code in _AUTH_FAILURE_ERRORS
    ):
        detail = error_code or response.status_code
        if error_description:
            detail = f"{detail}: {error_description}"
        raise AuthenticationError(
            f"token request rejected by the authentication authority: {detail}"
        )
    response.raise_for_status()
    return _as_dict(response.json())


def to_access_token(payload: dict[str, Any], clock: Clock) -> AccessToken:
    """Convert a token-endpoint response into an :class:`AccessToken`."""
    expires_in = payload.get("expires_in")
    lifetime = timedelta(seconds=int(expires_in)) if expires_in is not None else _DEFAULT_EXPIRES_IN
    return AccessToken(
        access_token=str(payload["access_token"]),
        token_type="Bearer",
        expires_at=clock.server_now() + lifetime,
    )


def is_near_expiry(token: AccessToken, clock: Clock, leeway: timedelta) -> bool:
    """Whether ``token`` should be refreshed now, accounting for ``leeway``."""
    return token.expires_at - clock.server_now() <= leeway


def build_client_assertion(
    *,
    issuer: str,
    client_id: str,
    signing_key: Any,
    signing_key_id: str,
    algorithm: str,
) -> str:
    """Sign a ``private_key_jwt`` client assertion with the registered key."""
    now = datetime.now(UTC)
    claims = {
        "iss": client_id,
        "sub": client_id,
        "aud": issuer,
        "jti": secrets.token_urlsafe(32),
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(
        claims,
        signing_key,
        algorithm=algorithm,
        headers={"kid": signing_key_id, "typ": CLIENT_ASSERTION_JWT_TYPE},
    )


def _oauth_error(response: httpx.Response) -> tuple[str | None, str | None]:
    try:
        body = response.json()
    except ValueError:
        return None, None
    if isinstance(body, dict):
        error = body.get("error")
        description = body.get("error_description")
        if isinstance(error, str):
            return error, description if isinstance(description, str) else None
    return None, None


def _as_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthenticationError("token endpoint returned a non-object response")
    return value

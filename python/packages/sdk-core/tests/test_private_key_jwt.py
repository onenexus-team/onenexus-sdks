from __future__ import annotations

import asyncio
from datetime import timedelta

import jwt
import pytest

from helpers import MockOidc, advance_clock, rsa_private_key_pem
from onenexus_sdk_core import (
    AuthenticationError,
    ClientContext,
    Credentials,
    PrivateKeyJwtCredentials,
    SystemClock,
)
from onenexus_sdk_core.credentials._oidc import CLIENT_ASSERTION_JWT_TYPE, JWT_BEARER_ASSERTION_TYPE


def _context() -> ClientContext:
    return ClientContext(clock=SystemClock(), refresh_leeway=timedelta(seconds=30))


def _creds(mock: MockOidc, **kwargs: object) -> PrivateKeyJwtCredentials:
    return PrivateKeyJwtCredentials(
        issuer=mock.issuer,
        client_id="acme-batch",
        signing_key=rsa_private_key_pem(),
        signing_key_id="acme-2026",
        transport=mock.transport(),
        sync_transport=mock.transport(),
        **kwargs,  # type: ignore[arg-type]
    )


def test_satisfies_credentials_protocol() -> None:
    mock = MockOidc()
    assert isinstance(_creds(mock), Credentials)


async def test_mints_with_private_key_jwt_assertion() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="pkj-at-1", expires_in=3600, scope="mlops:read")
    creds = _creds(mock, audience="mlops-api", scopes=("mlops:read",))

    token = await creds.resolve(_context())

    assert token.access_token == "pkj-at-1"
    form = mock.token_requests[0]
    assert form["grant_type"] == "client_credentials"
    assert form["client_id"] == "acme-batch"
    assert form["client_assertion_type"] == JWT_BEARER_ASSERTION_TYPE
    assert form["client_assertion"]
    header = jwt.get_unverified_header(form["client_assertion"])
    claims = jwt.decode(form["client_assertion"], options={"verify_signature": False})
    assert header["typ"] == CLIENT_ASSERTION_JWT_TYPE
    assert header["kid"] == "acme-2026"
    assert claims["iss"] == "acme-batch"
    assert claims["sub"] == "acme-batch"
    assert claims["aud"] == mock.issuer
    assert form["audience"] == "mlops-api"
    assert form["scope"] == "mlops:read"


async def test_caches_token_across_calls() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="pkj-cached", expires_in=3600)
    creds = _creds(mock)
    context = _context()

    first = await creds.resolve(context)
    second = await creds.resolve(context)

    assert first is second
    assert len(mock.token_requests) == 1


def test_resolve_sync_mints_with_private_key_jwt_assertion() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="pkj-sync", expires_in=3600)
    creds = _creds(mock, audience="mlops-api", scopes=("mlops:read",))

    token = creds.resolve_sync(_context())

    assert token.access_token == "pkj-sync"
    form = mock.token_requests[0]
    assert form["grant_type"] == "client_credentials"
    assert form["client_id"] == "acme-batch"
    assert form["client_assertion_type"] == JWT_BEARER_ASSERTION_TYPE
    header = jwt.get_unverified_header(form["client_assertion"])
    claims = jwt.decode(form["client_assertion"], options={"verify_signature": False})
    assert header["typ"] == CLIENT_ASSERTION_JWT_TYPE
    assert header["kid"] == "acme-2026"
    assert claims["iss"] == "acme-batch"
    assert claims["sub"] == "acme-batch"
    assert claims["aud"] == mock.issuer
    assert form["audience"] == "mlops-api"
    assert form["scope"] == "mlops:read"


async def test_single_flight_first_call() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="pkj-single", expires_in=3600)
    creds = _creds(mock)
    context = _context()

    tokens = await asyncio.gather(*(creds.resolve(context) for _ in range(3)))

    assert {t.access_token for t in tokens} == {"pkj-single"}
    assert len(mock.token_requests) == 1


async def test_remints_after_clock_advances() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="pkj-first", expires_in=3600)
    mock.queue_token(access_token="pkj-second", expires_in=3600)
    creds = _creds(mock)
    context = _context()

    first = await creds.resolve(context)
    advance_clock(context, 3700)
    second = await creds.resolve(context)

    assert first.access_token == "pkj-first"
    assert second.access_token == "pkj-second"
    assert len(mock.token_requests) == 2


async def test_omits_scope_and_audience_when_unset() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="pkj-min", expires_in=3600)
    await _creds(mock).resolve(_context())

    form = mock.token_requests[0]
    assert "scope" not in form
    assert "audience" not in form


async def test_rejection_maps_to_authentication_error() -> None:
    mock = MockOidc()
    mock.queue_error(401, "invalid_client", "client assertion signature failed")
    with pytest.raises(AuthenticationError, match="client assertion signature failed"):
        await _creds(mock).resolve(_context())


def test_resolve_sync_rejection_maps_to_authentication_error() -> None:
    mock = MockOidc()
    mock.queue_error(401, "invalid_client", "client assertion signature failed")
    with pytest.raises(AuthenticationError, match="client assertion signature failed"):
        _creds(mock).resolve_sync(_context())

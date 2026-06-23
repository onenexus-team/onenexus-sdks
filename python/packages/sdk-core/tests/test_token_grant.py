from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from helpers import MockOidc, advance_clock, far_future, soon
from onenexus_sdk_core import (
    AccessToken,
    AuthenticationError,
    ClientContext,
    Credentials,
    StaleCredentialsError,
    SystemClock,
    TokenGrantCredentials,
)


def _context() -> ClientContext:
    return ClientContext(clock=SystemClock(), refresh_leeway=timedelta(seconds=30))


def test_token_grant_satisfies_credentials_protocol() -> None:
    creds = TokenGrantCredentials(token=AccessToken("at", far_future()))
    assert isinstance(creds, Credentials)


async def test_returns_live_token_without_network() -> None:
    token = AccessToken("at-live", far_future())
    creds = TokenGrantCredentials(token=token)
    assert await creds.resolve(_context()) is token


def test_resolve_sync_returns_live_token_without_network() -> None:
    token = AccessToken("at-live", far_future())
    creds = TokenGrantCredentials(token=token)
    assert creds.resolve_sync(_context()) is token


async def test_stale_without_refresh_raises() -> None:
    creds = TokenGrantCredentials(token=AccessToken("at-old", soon(-3600)))
    with pytest.raises(StaleCredentialsError):
        await creds.resolve(_context())


def test_resolve_sync_stale_without_refresh_raises() -> None:
    creds = TokenGrantCredentials(token=AccessToken("at-old", soon(-3600)))
    with pytest.raises(StaleCredentialsError):
        creds.resolve_sync(_context())


async def test_refreshes_with_refresh_token_and_rotates() -> None:
    mock = MockOidc()
    mock.queue_token(
        access_token="refreshed-at",
        refresh_token="rotated-rt",
        expires_in=3600,
        scope="platform:read inference:invoke",
    )
    creds = TokenGrantCredentials(
        token=AccessToken("at-soon", soon(1)),
        refresh_token="initial-rt",
        issuer=mock.issuer,
        client_id="onenexus-portal",
        transport=mock.transport(),
    )

    token = await creds.resolve(_context())

    assert token.access_token == "refreshed-at"
    assert creds.scopes == ("platform:read", "inference:invoke")
    assert len(mock.token_requests) == 1
    form = mock.token_requests[0]
    assert form["grant_type"] == "refresh_token"
    assert form["refresh_token"] == "initial-rt"
    assert form["client_id"] == "onenexus-portal"


def test_resolve_sync_refreshes_with_refresh_token_and_rotates() -> None:
    mock = MockOidc()
    mock.queue_token(
        access_token="refreshed-at",
        refresh_token="rotated-rt",
        expires_in=3600,
        scope="platform:read inference:invoke",
    )
    creds = TokenGrantCredentials(
        token=AccessToken("at-soon", soon(1)),
        refresh_token="initial-rt",
        issuer=mock.issuer,
        client_id="onenexus-portal",
        sync_transport=mock.transport(),
    )

    token = creds.resolve_sync(_context())

    assert token.access_token == "refreshed-at"
    assert creds.scopes == ("platform:read", "inference:invoke")
    assert len(mock.token_requests) == 1
    form = mock.token_requests[0]
    assert form["grant_type"] == "refresh_token"
    assert form["refresh_token"] == "initial-rt"
    assert form["client_id"] == "onenexus-portal"


async def test_single_flight_concurrent_refresh() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="single-flight-at", expires_in=3600)
    creds = TokenGrantCredentials(
        token=AccessToken("at-soon", soon(1)),
        refresh_token="rt",
        issuer=mock.issuer,
        client_id="onenexus-portal",
        transport=mock.transport(),
    )

    tokens = await asyncio.gather(*(creds.resolve(_context()) for _ in range(3)))

    assert {t.access_token for t in tokens} == {"single-flight-at"}
    assert len(mock.token_requests) == 1


async def test_refreshes_again_after_clock_advances() -> None:
    mock = MockOidc()
    mock.queue_token(access_token="first-at", refresh_token="rt-2", expires_in=3600)
    mock.queue_token(access_token="second-at", refresh_token="rt-3", expires_in=3600)
    context = _context()
    creds = TokenGrantCredentials(
        token=AccessToken("at-soon", soon(1)),
        refresh_token="rt-1",
        issuer=mock.issuer,
        client_id="onenexus-portal",
        transport=mock.transport(),
    )

    first = await creds.resolve(context)
    advance_clock(context, 3700)
    second = await creds.resolve(context)

    assert first.access_token == "first-at"
    assert second.access_token == "second-at"
    assert mock.token_requests[1]["refresh_token"] == "rt-2"


async def test_refresh_rejection_maps_to_authentication_error() -> None:
    mock = MockOidc()
    mock.queue_error(401, "invalid_grant")
    creds = TokenGrantCredentials(
        token=AccessToken("at-soon", soon(1)),
        refresh_token="revoked-rt",
        issuer=mock.issuer,
        client_id="onenexus-portal",
        transport=mock.transport(),
    )

    with pytest.raises(AuthenticationError):
        await creds.resolve(_context())


def test_resolve_sync_refresh_rejection_maps_to_authentication_error() -> None:
    mock = MockOidc()
    mock.queue_error(401, "invalid_grant")
    creds = TokenGrantCredentials(
        token=AccessToken("at-soon", soon(1)),
        refresh_token="revoked-rt",
        issuer=mock.issuer,
        client_id="onenexus-portal",
        sync_transport=mock.transport(),
    )

    with pytest.raises(AuthenticationError):
        creds.resolve_sync(_context())


async def test_credential_leeway_overrides_context_leeway() -> None:
    token = AccessToken("at", soon(60))
    creds = TokenGrantCredentials(token=token, refresh_leeway=timedelta(seconds=10))
    context = ClientContext(clock=SystemClock(), refresh_leeway=timedelta(seconds=120))
    # 60s of life, credential leeway 10s -> still fresh even though context leeway is 120s.
    assert await creds.resolve(context) is token

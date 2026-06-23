from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from helpers import ClockCutoffCredentials, StaticCredentials
from onenexus_sdk_core import (
    AlreadyExistsError,
    AuthenticationError,
    ClientBase,
    ClientContext,
    PlatformError,
    RetryConfig,
    StaleCredentialsError,
    SystemClock,
)
from onenexus_sdk_core.http.transport import _retry_delay


class MockApi:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._responses: list[httpx.Response] = []

    def queue(self, response: httpx.Response) -> None:
        self._responses.append(response)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responses.pop(0)


def _client(api: MockApi, credentials: object, **kwargs: object) -> ClientBase:
    http = httpx.AsyncClient(transport=api.transport(), base_url="https://api.test")
    return ClientBase(
        base_url="https://api.test",
        credentials=credentials,  # type: ignore[arg-type]
        http=http,
        retry=RetryConfig(limit=2, base_delay=timedelta(0)),
        **kwargs,  # type: ignore[arg-type]
    )


async def test_sets_authorization_header() -> None:
    api = MockApi()
    api.queue(httpx.Response(200, json={"ok": True}))
    creds = StaticCredentials("at-x")

    async with _client(api, creds) as client:
        await client.request("POST", "/api/Ping", json={})

    assert api.requests[0].headers["authorization"] == "Bearer at-x"


async def test_observes_server_date_into_clock() -> None:
    api = MockApi()
    server_date = datetime.now(UTC) + timedelta(seconds=120)
    api.queue(
        httpx.Response(
            200, json={"ok": True}, headers={"date": format_datetime(server_date)}
        )
    )
    context = ClientContext(clock=SystemClock(), refresh_leeway=timedelta(seconds=30))

    async with _client(api, StaticCredentials(), context=context) as client:
        await client.request("POST", "/api/Ping", json={})

    assert context.clock.server_now() > datetime.now(UTC) + timedelta(seconds=110)


async def test_401_retry_advances_clock_then_succeeds() -> None:
    api = MockApi()
    cutoff = datetime.now(UTC) + timedelta(seconds=60)
    api.queue(
        httpx.Response(
            401,
            json={"code": "unauthenticated"},
            headers={
                "content-type": "application/problem+json",
                "date": format_datetime(cutoff + timedelta(seconds=1)),
            },
        )
    )
    api.queue(httpx.Response(200, json={"ok": True}))
    creds = ClockCutoffCredentials(cutoff)

    async with _client(api, creds) as client:
        response = await client.request("POST", "/api/Op", json={})

    assert response.json() == {"ok": True}
    auth_headers = [r.headers["authorization"] for r in api.requests]
    assert auth_headers == ["Bearer at-stale", "Bearer at-fresh"]
    assert creds.resolve_calls == 2


async def test_retry_limit_is_honored() -> None:
    api = MockApi()
    for _ in range(3):
        api.queue(
            httpx.Response(
                503,
                json={"code": "unavailable"},
                headers={"content-type": "application/problem+json"},
            )
        )

    async with _client(api, StaticCredentials()) as client:
        with pytest.raises(PlatformError):
            await client.request("POST", "/api/Op", json={})

    assert len(api.requests) == 3  # original + 2 retries


async def test_fail_fast_on_stale_credentials() -> None:
    api = MockApi()

    class Stale:
        async def resolve(self, context: ClientContext) -> object:
            raise StaleCredentialsError()

    async with _client(api, Stale()) as client:
        with pytest.raises(StaleCredentialsError):
            await client.request("POST", "/api/Op", json={})

    assert api.requests == []


async def test_fail_fast_on_authentication_error() -> None:
    api = MockApi()

    class Failing:
        async def resolve(self, context: ClientContext) -> object:
            raise AuthenticationError()

    async with _client(api, Failing()) as client:
        with pytest.raises(AuthenticationError):
            await client.request("POST", "/api/Op", json={})

    assert api.requests == []


async def test_problem_json_maps_to_typed_error() -> None:
    api = MockApi()
    api.queue(
        httpx.Response(
            409,
            json={"code": "already_exists", "detail": "exists", "requestId": "trace-1"},
            headers={"content-type": "application/problem+json"},
        )
    )

    async with _client(api, StaticCredentials()) as client:
        with pytest.raises(AlreadyExistsError) as excinfo:
            await client.request("POST", "/api/Op", json={})

    error = excinfo.value
    assert error.code == "already_exists"
    assert error.request_id == "trace-1"
    assert error.detail == "exists"


def test_retry_delay_is_jittered_and_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("onenexus_sdk_core.http.transport.random.random", lambda: 1.0)
    retry = RetryConfig(
        limit=5, base_delay=timedelta(seconds=1), backoff_limit=timedelta(seconds=4)
    )
    assert _retry_delay(1, retry) == 1.0  # 1 * 2**0
    assert _retry_delay(2, retry) == 2.0  # 1 * 2**1
    assert _retry_delay(4, retry) == 4.0  # 1 * 2**3 == 8, clamped to 4

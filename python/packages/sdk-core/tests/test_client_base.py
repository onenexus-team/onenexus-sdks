from __future__ import annotations

from datetime import timedelta

import httpx

from helpers import StaticCredentials
from onenexus_sdk_core import ClientBase
from onenexus_sdk_core.http import Transport


def test_client_base_satisfies_transport_protocol() -> None:
    client = ClientBase(
        base_url="https://api.test",
        credentials=StaticCredentials(),
        http=httpx.AsyncClient(base_url="https://api.test"),
    )
    assert isinstance(client, Transport)


async def test_request_returns_response_with_auth() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"value": 42})

    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.test"
    )
    async with ClientBase(
        base_url="https://api.test", credentials=StaticCredentials("at-1"), http=http
    ) as client:
        response = await client.request("POST", "/api/Get", json={"q": 1})

    assert response.json() == {"value": 42}
    assert requests[0].headers["authorization"] == "Bearer at-1"


async def test_client_level_refresh_leeway_threads_into_context() -> None:
    # A non-default refresh_leeway is accepted and applied to the client context.
    http = httpx.AsyncClient(base_url="https://api.test")
    client = ClientBase(
        base_url="https://api.test",
        credentials=StaticCredentials(),
        refresh_leeway=timedelta(seconds=90),
        http=http,
    )
    assert client._context.refresh_leeway == timedelta(seconds=90)
    await client.aclose()

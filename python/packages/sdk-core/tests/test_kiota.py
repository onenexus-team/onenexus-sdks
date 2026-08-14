from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from helpers import StaticCredentials
from kiota_abstractions.method import Method
from kiota_abstractions.request_information import RequestInformation
from onenexus_sdk_core import (
    ClientContext,
    OneNexusAccessTokenProvider,
    SystemClock,
    create_kiota_request_adapter,
)


async def test_access_token_provider_validates_allowed_hosts() -> None:
    credentials = StaticCredentials("at-test")
    context = ClientContext(
        clock=SystemClock(),
        refresh_leeway=timedelta(seconds=30),
    )
    provider = OneNexusAccessTokenProvider(
        credentials,
        context,
        allowed_hosts=["cas.test"],
    )

    assert await provider.get_authorization_token("https://other.test/api") == ""
    assert credentials.resolve_calls == 0
    assert await provider.get_authorization_token("https://cas.test/api") == "at-test"
    assert credentials.resolve_calls == 1


async def test_request_adapter_defaults_allowed_host_to_base_url() -> None:
    credentials = StaticCredentials("at-test")
    observed_authorization: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_authorization.append(request.headers.get("authorization"))
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        adapter = create_kiota_request_adapter(
            base_url="https://cas.test",
            credentials=credentials,
            http_client=http_client,
        )
        await adapter.send_no_response_content_async(
            RequestInformation(Method.GET, "https://other.test/api"),
            None,
        )
        await adapter.send_no_response_content_async(
            RequestInformation(Method.GET, "https://cas.test/api"),
            None,
        )

    assert observed_authorization == [None, "Bearer at-test"]
    assert credentials.resolve_calls == 1


@pytest.mark.parametrize("base_url", ["cas.test", "ftp://cas.test", "https:///api"])
def test_request_adapter_requires_absolute_http_base_url(base_url: str) -> None:
    with pytest.raises(ValueError, match=r"absolute HTTP\(S\) URL"):
        create_kiota_request_adapter(
            base_url=base_url,
            credentials=StaticCredentials("at-test"),
        )

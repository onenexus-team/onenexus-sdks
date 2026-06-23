from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
from onenexus_sdk_core import AccessToken, TokenGrantCredentials

from onenexus_cas_client import CasClient
from onenexus_cas_client.generated.models.assume_s3_role_request import AssumeS3RoleRequest
from onenexus_cas_client.generated.models.create_user_request import CreateUserRequest


def _credentials() -> TokenGrantCredentials:
    return TokenGrantCredentials(
        token=AccessToken("at-test", datetime(2030, 1, 1, tzinfo=UTC)),
    )


def _client(handler: httpx.MockTransport | httpx.AsyncBaseTransport) -> CasClient:
    http = httpx.AsyncClient(transport=handler, base_url="https://cas.test")
    return CasClient(base_url="https://cas.test", credentials=_credentials(), http_client=http)


async def test_create_user_routes_through_kiota_adapter() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "user": {
                    "userId": "0193fabc-1234-7def-abcd-1234567890ab",
                    "tenantId": "0193fabc-1234-7def-abcd-1234567890ac",
                    "email": "a@b.c",
                    "displayName": "A B",
                    "emailConfirmed": False,
                    "createdAt": "2026-05-13T10:00:00Z",
                },
                "acceptInvitationUrl": "https://portal.acme.com/accept?token=abc",
                "acceptInvitationExpiresAt": "2026-05-20T10:00:00Z",
            },
            headers={"content-type": "application/json"},
        )

    async with _client(httpx.MockTransport(handler)) as cas:
        result = await cas.create_user(
            CreateUserRequest(
                email="a@b.c",
                display_name="A B",
                client_token="01HV8XR4D0YPRNNK8YY8VJ3QK2",
            )
        )

    assert captured["path"] == "/api/CreateUser"
    assert captured["auth"] == "Bearer at-test"
    assert captured["body"] == {
        "email": "a@b.c",
        "displayName": "A B",
        "clientToken": "01HV8XR4D0YPRNNK8YY8VJ3QK2",
    }
    assert result.user is not None
    assert result.user.email == "a@b.c"
    assert str(result.user.user_id) == "0193fabc-1234-7def-abcd-1234567890ab"


async def test_assume_s3_role_parses_kiota_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "accessKeyId": "AKIA",
                "secretAccessKey": "secret",
                "sessionToken": "token",
                "expiration": "2026-05-13T11:00:00Z",
            },
            headers={"content-type": "application/json"},
        )

    async with _client(httpx.MockTransport(handler)) as cas:
        result = await cas.assume_s3_role(AssumeS3RoleRequest(role_name="reader"))

    assert result.access_key_id == "AKIA"
    assert result.session_token == "token"

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from kiota_abstractions.api_error import APIError
from onenexus_sdk_core import (
    AccessToken,
    ClientContext,
    SystemClock,
    TokenGrantCredentials,
)

from onenexus_cas_client import (
    AssignRoleRequest,
    AttachPolicyToRoleRequest,
    CasClient,
    CreateAuthorizationRoleRequest,
    DeleteAuthorizationRoleRequest,
    DetachPolicyFromRoleRequest,
    ListPolicyAttachmentsRequest,
    ListRolePoliciesRequest,
    RemoveRoleAssignmentRequest,
    RemoveServiceClientKeyRequest,
    ResendUserInvitationRequest,
    UpdateAuthorizationRoleDescriptionRequest,
)
from onenexus_cas_client.generated.models.assume_s3_role_request import AssumeS3RoleRequest
from onenexus_cas_client.generated.models.create_user_request import CreateUserRequest
from onenexus_cas_client.generated.models.disable_service_client_request import (
    DisableServiceClientRequest,
)


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
                    "userUri": "onenexus:user/0193fabc-1234-7def-abcd-1234567890ab",
                    "tenantId": "0193fabc-1234-7def-abcd-1234567890ac",
                    "email": "a@b.c",
                    "displayName": "A B",
                    "emailConfirmed": False,
                    "createdAt": "2026-05-13T10:00:00Z",
                },
            },
            headers={"content-type": "application/json"},
        )

    async with _client(httpx.MockTransport(handler)) as cas:
        result = await cas.create_user(
            CreateUserRequest(
                email="a@b.c",
                display_name="A B",
                request_id="01HV8XR4D0YPRNNK8YY8VJ3QK2",
            )
        )

    assert captured["path"] == "/api/CreateUser"
    assert captured["auth"] == "Bearer at-test"
    assert captured["body"] == {
        "email": "a@b.c",
        "displayName": "A B",
        "requestId": "01HV8XR4D0YPRNNK8YY8VJ3QK2",
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


async def test_authorization_and_user_list_methods_route_through_kiota() -> None:
    captured_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        return httpx.Response(
            200,
            json={},
            headers={"content-type": "application/json"},
        )

    async with _client(httpx.MockTransport(handler)) as cas:
        await cas.list_users()
        await cas.create_role(CreateAuthorizationRoleRequest())
        await cas.update_role_description(
            UpdateAuthorizationRoleDescriptionRequest(
                request_id="request-2",
                role_uri="onenexus:role/Reader",
                description="Read-only access",
            )
        )
        await cas.list_roles()
        await cas.delete_role(DeleteAuthorizationRoleRequest())
        await cas.assign_role(AssignRoleRequest())
        await cas.remove_role_assignment(RemoveRoleAssignmentRequest())
        await cas.list_role_assignments()
        await cas.attach_policy_to_role(AttachPolicyToRoleRequest())
        await cas.detach_policy_from_role(DetachPolicyFromRoleRequest())
        await cas.list_policy_attachments(ListPolicyAttachmentsRequest())
        await cas.list_role_policies(ListRolePoliciesRequest())

    assert captured_paths == [
        "/api/ListUsers",
        "/api/CreateRole",
        "/api/UpdateRoleDescription",
        "/api/ListRoles",
        "/api/DeleteRole",
        "/api/AssignRole",
        "/api/RemoveRoleAssignment",
        "/api/ListRoleAssignments",
        "/api/AttachPolicyToRole",
        "/api/DetachPolicyFromRole",
        "/api/ListPolicyAttachments",
        "/api/ListRolePolicies",
    ]


async def test_service_client_key_management_and_invitation_resend_route_through_kiota() -> None:
    captured: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append((request.url.path, json.loads(request.content)))
        if request.url.path == "/api/ResendUserInvitation":
            return httpx.Response(204)
        return httpx.Response(
            200, json={"serviceClient": {}}, headers={"content-type": "application/json"}
        )

    async with _client(httpx.MockTransport(handler)) as cas:
        await cas.remove_service_client_key(
            RemoveServiceClientKeyRequest(
                service_client_id="0193fabc-1234-7def-abcd-1234567890ab", kid="key-1"
            )
        )
        await cas.disable_service_client(
            DisableServiceClientRequest(service_client_id="0193fabc-1234-7def-abcd-1234567890ab")
        )
        await cas.resend_user_invitation(
            ResendUserInvitationRequest(user_id="0193fabc-1234-7def-abcd-1234567890ac")
        )

    assert captured == [
        (
            "/api/RemoveServiceClientKey",
            {"serviceClientId": "0193fabc-1234-7def-abcd-1234567890ab", "kid": "key-1"},
        ),
        ("/api/DisableServiceClient", {"serviceClientId": "0193fabc-1234-7def-abcd-1234567890ab"}),
        ("/api/ResendUserInvitation", {"userId": "0193fabc-1234-7def-abcd-1234567890ac"}),
    ]


async def test_retryable_post_uses_kiota_retry_middleware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[tuple[str | None, str | None, bytes]] = []
    retry_sleep = AsyncMock()
    monkeypatch.setattr("kiota_http.middleware.retry_handler.asyncio.sleep", retry_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(
            (
                request.headers.get("authorization"),
                request.headers.get("x-caller-header"),
                request.content,
            )
        )
        if len(attempts) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={}, headers={"content-type": "application/json"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://cas.test",
        headers={"x-caller-header": "stable"},
    ) as http:
        async with CasClient(
            base_url="https://cas.test",
            credentials=_credentials(),
            http_client=http,
        ) as cas:
            await cas.create_user(CreateUserRequest(email="a@b.c", display_name="A B"))

        assert not http.is_closed

    assert len(attempts) == 2
    assert attempts[0] == attempts[1]
    assert attempts[0][0] == "Bearer at-test"
    assert attempts[0][1] == "stable"
    retry_sleep.assert_awaited_once()


async def test_non_retryable_post_is_not_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            409,
            json={"title": "Conflict"},
            headers={"content-type": "application/problem+json"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://cas.test",
    ) as http:
        async with CasClient(
            base_url="https://cas.test",
            credentials=_credentials(),
            http_client=http,
        ) as cas:
            with pytest.raises(APIError):
                await cas.create_user(CreateUserRequest(email="a@b.c", display_name="A B"))

    assert attempts == 1


async def test_injected_http_client_preserves_hooks_and_observes_server_date() -> None:
    server_date = datetime.now(UTC) + timedelta(seconds=120)
    caller_hook = AsyncMock()
    context = ClientContext(
        clock=SystemClock(),
        refresh_leeway=timedelta(seconds=30),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={},
            headers={
                "content-type": "application/json",
                "date": format_datetime(server_date),
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://cas.test",
        event_hooks={"response": [caller_hook]},
    ) as http:
        async with CasClient(
            base_url="https://cas.test",
            credentials=_credentials(),
            context=context,
            http_client=http,
        ) as cas:
            await cas.list_users()

    caller_hook.assert_awaited_once()
    assert context.clock.server_now() > datetime.now(UTC) + timedelta(seconds=110)


async def test_cas_client_closes_owned_http_client() -> None:
    cas = CasClient(base_url="https://cas.test", credentials=_credentials())
    owned_http = cas._http_client

    async with cas:
        pass

    assert owned_http.is_closed

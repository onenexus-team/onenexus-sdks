from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from kiota_abstractions.request_option import RequestOption
from kiota_http.kiota_client_factory import KiotaClientFactory
from kiota_http.middleware.options.retry_handler_option import RetryHandlerOption
from onenexus_sdk_core import AccessToken, TokenGrantCredentials

from onenexus_cas_client import (
    AddServiceClientKeyRequest,
    AssignRoleRequest,
    AttachPolicyToRoleRequest,
    CasClient,
    CreateAuthorizationRoleRequest,
    CreateServiceClientRequest,
    DeleteAuthorizationRoleRequest,
    DeletePolicyRequest,
    DetachPolicyFromRoleRequest,
    ListPolicyAttachmentsRequest,
    ListRolePoliciesRequest,
    PublishPolicyRequest,
    RemoveRoleAssignmentRequest,
    RemoveServiceClientKeyRequest,
    ResendUserInvitationRequest,
    UpdateAuthorizationRoleDescriptionRequest,
    UpdatePolicyRequest,
    UpdateProfileRequest,
)
from onenexus_cas_client.generated.models.assume_s3_role_request import AssumeS3RoleRequest
from onenexus_cas_client.generated.models.create_user_request import CreateUserRequest
from onenexus_cas_client.generated.models.disable_service_client_request import (
    DisableServiceClientRequest,
)

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{16,128}$")


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
        captured["idempotency_key"] = request.headers.get("x-nx1-idempotency-key")
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
            )
        )

    assert captured["path"] == "/api/CreateUser"
    assert captured["auth"] == "Bearer at-test"
    assert isinstance(captured["idempotency_key"], str)
    assert IDEMPOTENCY_KEY_PATTERN.fullmatch(captured["idempotency_key"])
    assert captured["body"] == {
        "email": "a@b.c",
        "displayName": "A B",
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
    captured_idempotency_keys: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        idempotency_key = request.headers.get("x-nx1-idempotency-key")
        if idempotency_key is not None:
            captured_idempotency_keys.append((request.url.path, idempotency_key))
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
    assert [path for path, _ in captured_idempotency_keys] == [
        "/api/CreateRole",
        "/api/UpdateRoleDescription",
        "/api/DeleteRole",
        "/api/AssignRole",
        "/api/RemoveRoleAssignment",
        "/api/AttachPolicyToRole",
        "/api/DetachPolicyFromRole",
    ]
    assert all(
        IDEMPOTENCY_KEY_PATTERN.fullmatch(key) for _, key in captured_idempotency_keys
    )


async def test_service_client_key_management_and_invitation_resend_route_through_kiota() -> None:
    captured: list[tuple[str, dict[str, object], str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            (
                request.url.path,
                json.loads(request.content),
                request.headers.get("x-nx1-idempotency-key"),
            )
        )
        if request.url.path == "/api/ResendUserInvitation":
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={"serviceClient": {}},
            headers={"content-type": "application/json"},
        )

    service_client_id = UUID("0193fabc-1234-7def-abcd-1234567890ab")
    async with _client(httpx.MockTransport(handler)) as cas:
        await cas.create_service_client(
            CreateServiceClientRequest(display_name="worker", public_jwk="{}")
        )
        await cas.add_service_client_key(
            AddServiceClientKeyRequest(service_client_id=service_client_id, public_jwk="{}")
        )
        await cas.remove_service_client_key(
            RemoveServiceClientKeyRequest(service_client_id=service_client_id, kid="key-1")
        )
        await cas.disable_service_client(
            DisableServiceClientRequest(service_client_id=service_client_id)
        )
        await cas.resend_user_invitation(
            ResendUserInvitationRequest(
                user_id=UUID("0193fabc-1234-7def-abcd-1234567890ac")
            )
        )

    assert [(path, body) for path, body, _ in captured] == [
        ("/api/CreateServiceClient", {"displayName": "worker", "publicJwk": "{}"}),
        (
            "/api/AddServiceClientKey",
            {"publicJwk": "{}", "serviceClientId": str(service_client_id)},
        ),
        (
            "/api/RemoveServiceClientKey",
            {"serviceClientId": str(service_client_id), "kid": "key-1"},
        ),
        ("/api/DisableServiceClient", {"serviceClientId": str(service_client_id)}),
        (
            "/api/ResendUserInvitation",
            {"userId": "0193fabc-1234-7def-abcd-1234567890ac"},
        ),
    ]
    assert all(
        key is not None and IDEMPOTENCY_KEY_PATTERN.fullmatch(key)
        for _, _, key in captured
    )


async def test_policy_and_profile_methods_route_through_kiota() -> None:
    captured: list[tuple[str, dict[str, object], str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            (
                request.url.path,
                json.loads(request.content),
                request.headers.get("x-nx1-idempotency-key"),
            )
        )
        response = {"displayName": "Updated User"} if request.url.path == "/account/profile" else {}
        return httpx.Response(
            200,
            json=response,
            headers={"content-type": "application/json"},
        )

    async with _client(httpx.MockTransport(handler)) as cas:
        await cas.publish_policy(PublishPolicyRequest(name="object-reader"))
        await cas.update_policy(
            UpdatePolicyRequest(
                name="object-reader",
                expected_content_state_token="state-1",
            )
        )
        await cas.delete_policy(
            DeletePolicyRequest(
                name="object-reader",
                expected_content_state_token="state-2",
            )
        )
        profile = await cas.update_profile(
            UpdateProfileRequest(
                update_mask=["displayName"],
                display_name="Updated User",
            )
        )

    assert [path for path, _, _ in captured] == [
        "/api/PublishPolicy",
        "/api/UpdatePolicy",
        "/api/DeletePolicy",
        "/account/profile",
    ]
    assert captured[-1][1] == {
        "displayName": "Updated User",
        "updateMask": ["displayName"],
    }
    assert all(
        key is not None and IDEMPOTENCY_KEY_PATTERN.fullmatch(key)
        for _, _, key in captured
    )
    assert profile.display_name == "Updated User"


async def test_idempotency_key_is_reused_when_kiota_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []
    uuid_calls = 0

    def fake_uuid4() -> UUID:
        nonlocal uuid_calls
        uuid_calls += 1
        return UUID("12345678-1234-5678-1234-567812345678")

    async def skip_retry_delay(_: float) -> None:
        return None

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.headers["x-nx1-idempotency-key"])
        if len(attempts) == 1:
            return httpx.Response(
                503,
                json={"title": "temporarily unavailable"},
                headers={"content-type": "application/problem+json"},
            )
        return httpx.Response(
            200,
            json={},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr("onenexus_cas_client.client.uuid4", fake_uuid4)
    monkeypatch.setattr("kiota_http.middleware.retry_handler.asyncio.sleep", skip_retry_delay)
    retry_options: dict[str, RequestOption] = {
        "RetryHandlerOption": RetryHandlerOption(delay=0, max_retries=1)
    }
    base_http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://cas.test",
    )
    retry_http = KiotaClientFactory.create_with_default_middleware(base_http, retry_options)

    async with retry_http:
        cas = CasClient(
            base_url="https://cas.test",
            credentials=_credentials(),
            http_client=retry_http,
        )
        await cas.create_user(CreateUserRequest(email="a@b.c", display_name="A B"))

    expected_key = "12345678123456781234567812345678"
    assert uuid_calls == 1
    assert attempts == [expected_key, expected_key]

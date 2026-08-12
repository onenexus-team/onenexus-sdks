from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
from onenexus_sdk_core import AccessToken, TokenGrantCredentials

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
)
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

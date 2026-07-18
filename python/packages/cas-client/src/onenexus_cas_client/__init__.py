"""``onenexus-cas-client`` — typed async client for the Central Auth Service.

The ``CasClient`` facade is hand-written; the request/response models and
request builders under ``generated`` are produced by Microsoft Kiota from
``specs/cas/openapi.json``. Credential primitives live in ``onenexus-sdk-core``
and are adapted to Kiota's request adapter.
"""

from __future__ import annotations

from . import generated
from .client import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    AddServiceClientKeyRequest,
    AddServiceClientKeyResponse,
    AssignRoleRequest,
    AssignRoleResponse,
    AssumeS3RoleRequest,
    AssumeS3RoleResponse,
    AttachPolicyToRoleRequest,
    AttachPolicyToRoleResponse,
    AuthorizationRelationshipRemovedResponse,
    CasClient,
    CreateAuthorizationRoleRequest,
    CreateAuthorizationRoleResponse,
    CreateServiceClientRequest,
    CreateServiceClientResponse,
    CreateUserRequest,
    CreateUserResponse,
    DeleteAuthorizationRoleRequest,
    DeleteAuthorizationRoleResponse,
    DetachPolicyFromRoleRequest,
    ListAuthorizationRolesRequest,
    ListAuthorizationRolesResponse,
    ListPolicyAttachmentsRequest,
    ListPolicyAttachmentsResponse,
    ListRoleAssignmentsRequest,
    ListRoleAssignmentsResponse,
    ListRolePoliciesRequest,
    ListS3RolesResponse,
    ListServiceClientsResponse,
    ListTenantUsersResponse,
    ListUsersRequest,
    RemoveRoleAssignmentRequest,
)

__all__ = [
    "AcceptInvitationRequest",
    "AcceptInvitationResponse",
    "AddServiceClientKeyRequest",
    "AddServiceClientKeyResponse",
    "AssignRoleRequest",
    "AssignRoleResponse",
    "AssumeS3RoleRequest",
    "AssumeS3RoleResponse",
    "AttachPolicyToRoleRequest",
    "AttachPolicyToRoleResponse",
    "AuthorizationRelationshipRemovedResponse",
    "CasClient",
    "CreateAuthorizationRoleRequest",
    "CreateAuthorizationRoleResponse",
    "CreateServiceClientRequest",
    "CreateServiceClientResponse",
    "CreateUserRequest",
    "CreateUserResponse",
    "DeleteAuthorizationRoleRequest",
    "DeleteAuthorizationRoleResponse",

    "DetachPolicyFromRoleRequest",

    "ListAuthorizationRolesRequest",
    "ListAuthorizationRolesResponse",

    "ListPolicyAttachmentsRequest",
    "ListPolicyAttachmentsResponse",
    "ListRoleAssignmentsRequest",
    "ListRoleAssignmentsResponse",
    "ListRolePoliciesRequest",
    "ListS3RolesResponse",
    "ListServiceClientsResponse",
    "ListTenantUsersResponse",
    "ListUsersRequest",

    "RemoveRoleAssignmentRequest",

    "generated",
]

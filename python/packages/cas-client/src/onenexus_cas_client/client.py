"""Typed async client for the OneNexus Central Auth Service Customer API.

Hand-written facade over the Kiota-generated client. The generated code owns the
OpenAPI surface; this facade gives applications a flat, ergonomic API and wires
Kiota's request adapter to OneNexus credentials.
"""

from __future__ import annotations

import httpx
from onenexus_sdk_core import ClientContext, Credentials, create_kiota_request_adapter

from .generated.cas_generated_client import CasGeneratedClient
from .generated.models.accept_invitation_request import AcceptInvitationRequest
from .generated.models.accept_invitation_response import AcceptInvitationResponse
from .generated.models.add_service_client_key_request import AddServiceClientKeyRequest
from .generated.models.add_service_client_key_response import AddServiceClientKeyResponse
from .generated.models.assign_role_request import AssignRoleRequest
from .generated.models.assign_role_response import AssignRoleResponse
from .generated.models.assume_s3_role_request import AssumeS3RoleRequest
from .generated.models.assume_s3_role_response import AssumeS3RoleResponse
from .generated.models.attach_policy_to_role_request import AttachPolicyToRoleRequest
from .generated.models.attach_policy_to_role_response import AttachPolicyToRoleResponse
from .generated.models.authorization_relationship_removed_response import (
    AuthorizationRelationshipRemovedResponse,
)
from .generated.models.create_authorization_role_request import CreateAuthorizationRoleRequest
from .generated.models.create_authorization_role_response import CreateAuthorizationRoleResponse
from .generated.models.create_service_client_request import CreateServiceClientRequest
from .generated.models.create_service_client_response import CreateServiceClientResponse
from .generated.models.create_user_request import CreateUserRequest
from .generated.models.create_user_response import CreateUserResponse
from .generated.models.delete_authorization_role_request import DeleteAuthorizationRoleRequest
from .generated.models.delete_authorization_role_response import DeleteAuthorizationRoleResponse
from .generated.models.disable_service_client_request import DisableServiceClientRequest
from .generated.models.disable_service_client_response import DisableServiceClientResponse
from .generated.models.detach_policy_from_role_request import DetachPolicyFromRoleRequest
from .generated.models.empty_s3_request import EmptyS3Request
from .generated.models.empty_service_client_request import EmptyServiceClientRequest
from .generated.models.list_authorization_roles_request import ListAuthorizationRolesRequest
from .generated.models.list_authorization_roles_response import ListAuthorizationRolesResponse
from .generated.models.list_policy_attachments_request import ListPolicyAttachmentsRequest
from .generated.models.list_policy_attachments_response import ListPolicyAttachmentsResponse
from .generated.models.list_role_assignments_request import ListRoleAssignmentsRequest
from .generated.models.list_role_assignments_response import ListRoleAssignmentsResponse
from .generated.models.list_role_policies_request import ListRolePoliciesRequest
from .generated.models.list_s3_roles_response import ListS3RolesResponse
from .generated.models.list_service_clients_response import ListServiceClientsResponse
from .generated.models.list_users_request import ListUsersRequest
from .generated.models.list_users_response import ListUsersResponse
from .generated.models.remove_role_assignment_request import RemoveRoleAssignmentRequest
from .generated.models.remove_service_client_key_request import RemoveServiceClientKeyRequest
from .generated.models.remove_service_client_key_response import RemoveServiceClientKeyResponse
from .generated.models.resend_user_invitation_request import ResendUserInvitationRequest
from .generated.models.update_authorization_role_description_request import (
    UpdateAuthorizationRoleDescriptionRequest,
)
from .generated.models.update_authorization_role_description_response import (
    UpdateAuthorizationRoleDescriptionResponse,
)


class CasClient:
    """Async client for the CAS Customer API (``/api/*``)."""

    def __init__(
        self,
        *,
        base_url: str,
        credentials: Credentials,
        context: ClientContext | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_http = http_client is None
        self._http_client = http_client or httpx.AsyncClient(base_url=base_url)
        self._adapter = create_kiota_request_adapter(
            base_url=base_url,
            credentials=credentials,
            context=context,
            http_client=self._http_client,
        )
        self._client = CasGeneratedClient(self._adapter)

    async def create_user(self, request: CreateUserRequest) -> CreateUserResponse:
        """
        Admin invites a user into their own tenant and triggers the invite email.

        CAS derives the tenant from the caller's access token. The user stays pending until they redeem
        the emailed invitation and set a password.

        API operation: POST /api/CreateUser.
        """
        response = await self._client.api.create_user.post(request)
        if response is None:
            raise RuntimeError("CAS CreateUser returned no response body")
        return response

    async def list_users(
        self, request: ListUsersRequest | None = None
    ) -> ListUsersResponse:
        """
        Lists users in the authenticated caller's own tenant.

        CAS always lists the caller's tenant; do not send a tenant identifier. Results include root and
        member users. Send one returned cursor at a time to move backward or forward through the list.

        API operation: POST /api/ListUsers.
        """
        response = await self._client.api.list_users.post(request or ListUsersRequest())
        if response is None:
            raise RuntimeError("CAS ListUsers returned no response body")
        return response

    async def accept_invitation(
        self, request: AcceptInvitationRequest
    ) -> AcceptInvitationResponse:
        """
        Redeems an invitation, sets a password, and activates the account.

        This endpoint does not require an access token. It accepts the invitation details delivered by
        email, and an invitation can be used only once. On success, follow `loginUrl` to sign in.

        API operation: POST /api/AcceptInvitation.
        """
        response = await self._client.api.accept_invitation.post(request)
        if response is None:
            raise RuntimeError("CAS AcceptInvitation returned no response body")
        return response

    async def list_s3_roles(self) -> ListS3RolesResponse:
        """
        List the S3 IAM roles provisioned in the caller's tenant account.

        CAS derives the tenant from the access token; this request cannot list another tenant's S3
        roles. Each result includes the role's trust and inline permission policies for display in
        tenant administration tools.

        API operation: POST /api/ListS3Roles.
        """
        response = await self._client.api.list_s3_roles.post(EmptyS3Request())
        if response is None:
            raise RuntimeError("CAS ListS3Roles returned no response body")
        return response

    async def assume_s3_role(self, request: AssumeS3RoleRequest) -> AssumeS3RoleResponse:
        """
        Assume an S3 role in the caller's tenant account and return temporary credentials.

        CAS authorizes the requested role before issuing credentials. Use the returned access key,
        secret, and session token for S3 requests until `expiration`; never persist or share the
        temporary secret.

        API operation: POST /api/AssumeS3Role.
        """
        response = await self._client.api.assume_s3_role.post(request)
        if response is None:
            raise RuntimeError("CAS AssumeS3Role returned no response body")
        return response

    async def list_service_clients(self) -> ListServiceClientsResponse:
        """
        List OAuth service clients owned by the caller's tenant.

        CAS derives the tenant from the access token. The response includes client identifiers and
        registered public keys, never private keys.

        API operation: POST /api/ListServiceClients.
        """
        response = await self._client.api.list_service_clients.post(EmptyServiceClientRequest())
        if response is None:
            raise RuntimeError("CAS ListServiceClients returned no response body")
        return response

    async def create_service_client(
        self, request: CreateServiceClientRequest
    ) -> CreateServiceClientResponse:
        """
        Create a tenant-owned service client with its first browser-generated public assertion key.

        Generate the key pair in your application or browser and submit only the public JWK. CAS returns
        the `clientId` needed at the token endpoint; it never receives or stores the corresponding
        private key.

        API operation: POST /api/CreateServiceClient.
        """
        response = await self._client.api.create_service_client.post(request)
        if response is None:
            raise RuntimeError("CAS CreateServiceClient returned no response body")
        return response

    async def add_service_client_key(
        self, request: AddServiceClientKeyRequest
    ) -> AddServiceClientKeyResponse:
        """
        Add an additional public assertion key to a service client.

        Use this to rotate a client key without interrupting the old key. CAS accepts at most three
        public keys per service client; retain the private key outside CAS.

        API operation: POST /api/AddServiceClientKey.
        """
        response = await self._client.api.add_service_client_key.post(request)
        if response is None:
            raise RuntimeError("CAS AddServiceClientKey returned no response body")
        return response

    async def remove_service_client_key(
        self, request: RemoveServiceClientKeyRequest
    ) -> RemoveServiceClientKeyResponse:
        """
        Revokes one public assertion key from a service client.

        The final key cannot be removed. Disable the service client when its only key is compromised.

        API operation: POST /api/RemoveServiceClientKey.
        """
        response = await self._client.api.remove_service_client_key.post(request)
        if response is None:
            raise RuntimeError("CAS RemoveServiceClientKey returned no response body")
        return response

    async def disable_service_client(
        self, request: DisableServiceClientRequest
    ) -> DisableServiceClientResponse:
        """
        Disables a service client so it cannot obtain new access tokens.

        The operation is idempotent. Already-issued short-lived access tokens retain their normal
        expiry; disabling prevents subsequent token issuance.

        API operation: POST /api/DisableServiceClient.
        """
        response = await self._client.api.disable_service_client.post(request)
        if response is None:
            raise RuntimeError("CAS DisableServiceClient returned no response body")
        return response

    async def resend_user_invitation(self, request: ResendUserInvitationRequest) -> None:
        """
        Re-sends an invitation to a pending member in the caller's tenant.

        CAS derives the tenant from the authenticated caller. Tenant roots and users in other tenants
        cannot be targeted through this operation.

        API operation: POST /api/ResendUserInvitation.
        """
        await self._client.api.resend_user_invitation.post(request)

    async def create_role(
        self, request: CreateAuthorizationRoleRequest
    ) -> CreateAuthorizationRoleResponse:
        """
        Idempotently creates one tenant authorization role.

        Role names are case-sensitive ASCII letters and digits. The role is scoped to the caller's
        tenant; creating an existing role with the same name succeeds and returns `created: false`.

        API operation: POST /api/CreateRole.
        """
        response = await self._client.api.create_role.post(request)
        if response is None:
            raise RuntimeError("CAS CreateRole returned no response body")
        return response

    async def update_role_description(
        self, request: UpdateAuthorizationRoleDescriptionRequest
    ) -> UpdateAuthorizationRoleDescriptionResponse:
        """Update a tenant role's optional human-readable description.

        API operation: ``POST /api/UpdateRoleDescription``.
        """
        response = await self._client.api.update_role_description.post(request)
        if response is None:
            raise RuntimeError("CAS UpdateRoleDescription returned no response body")
        return response

    async def list_roles(
        self, request: ListAuthorizationRolesRequest | None = None
    ) -> ListAuthorizationRolesResponse:
        """
        Lists authorization roles in the caller's tenant.

        Results are ordered by role name. The returned `roleUri` is the stable identifier to use when
        assigning roles or attaching policies.

        API operation: POST /api/ListRoles.
        """
        response = await self._client.api.list_roles.post(
            request or ListAuthorizationRolesRequest()
        )
        if response is None:
            raise RuntimeError("CAS ListRoles returned no response body")
        return response

    async def delete_role(
        self, request: DeleteAuthorizationRoleRequest
    ) -> DeleteAuthorizationRoleResponse:
        """
        Deletes one unreferenced tenant authorization role. Direct grants, workload bindings, and policy
        attachments must be removed explicitly before deletion; CAS never cascades those relationships.

        Remove every direct user, service-client, workload, and policy relationship first. CAS does not
        cascade deletion, which prevents a role from disappearing unexpectedly from an access
        configuration.

        API operation: POST /api/DeleteRole.
        """
        response = await self._client.api.delete_role.post(request)
        if response is None:
            raise RuntimeError("CAS DeleteRole returned no response body")
        return response

    async def assign_role(self, request: AssignRoleRequest) -> AssignRoleResponse:
        """
        Idempotently assigns one role to a user or service client.

        The assignee and role must belong to the caller's tenant. Repeating the same request does not
        create a second assignment; inspect `created` to tell whether CAS created it on this call.

        API operation: POST /api/AssignRole.
        """
        response = await self._client.api.assign_role.post(request)
        if response is None:
            raise RuntimeError("CAS AssignRole returned no response body")
        return response

    async def remove_role_assignment(
        self, request: RemoveRoleAssignmentRequest
    ) -> AuthorizationRelationshipRemovedResponse:
        """
        Removes one direct role assignment using its current state token.

        First obtain the assignment with `ListRoleAssignments`, then send its `stateToken`. CAS rejects
        a stale token so an administrator cannot remove a relationship that changed after it was
        displayed.

        API operation: POST /api/RemoveRoleAssignment.
        """
        response = await self._client.api.remove_role_assignment.post(request)
        if response is None:
            raise RuntimeError("CAS RemoveRoleAssignment returned no response body")
        return response

    async def list_role_assignments(
        self, request: ListRoleAssignmentsRequest | None = None
    ) -> ListRoleAssignmentsResponse:
        """
        Lists direct assignments by exactly one role or assignee filter.

        Provide exactly one of `roleUri` or `assignee`. Use the returned `before` or `after` value
        unchanged to navigate pages; do not send both cursors in one request.

        API operation: POST /api/ListRoleAssignments.
        """
        response = await self._client.api.list_role_assignments.post(
            request or ListRoleAssignmentsRequest()
        )
        if response is None:
            raise RuntimeError("CAS ListRoleAssignments returned no response body")
        return response

    async def attach_policy_to_role(
        self, request: AttachPolicyToRoleRequest
    ) -> AttachPolicyToRoleResponse:
        """
        Compiles and idempotently attaches one tenant- or platform-managed policy to a role.

        A direct attachment makes the policy available whenever the role is evaluated. Repeating the
        same request preserves the existing relationship and returns `created: false`.

        API operation: POST /api/AttachPolicyToRole.
        """
        response = await self._client.api.attach_policy_to_role.post(request)
        if response is None:
            raise RuntimeError("CAS AttachPolicyToRole returned no response body")
        return response

    async def detach_policy_from_role(
        self, request: DetachPolicyFromRoleRequest
    ) -> AuthorizationRelationshipRemovedResponse:
        """
        Detaches one policy from one role using the relationship state token.

        Get the attachment first with `ListPolicyAttachments` or `ListRolePolicies`, then provide its
        `stateToken`. This protects against deleting a relationship that changed concurrently.

        API operation: POST /api/DetachPolicyFromRole.
        """
        response = await self._client.api.detach_policy_from_role.post(request)
        if response is None:
            raise RuntimeError("CAS DetachPolicyFromRole returned no response body")
        return response

    async def list_policy_attachments(
        self, request: ListPolicyAttachmentsRequest
    ) -> ListPolicyAttachmentsResponse:
        """
        Lists roles to which one policy is directly attached.

        The response contains the direct policy-to-role relationships, not the users or service clients
        that inherit access through those roles. Use the returned cursors for paging.

        API operation: POST /api/ListPolicyAttachments.
        """
        response = await self._client.api.list_policy_attachments.post(request)
        if response is None:
            raise RuntimeError("CAS ListPolicyAttachments returned no response body")
        return response

    async def list_role_policies(
        self, request: ListRolePoliciesRequest
    ) -> ListPolicyAttachmentsResponse:
        """
        Lists tenant- and platform-managed policies directly attached to one role.

        This returns only direct attachments. A policy inherited by another mechanism is not included.
        Use the returned cursors for paging.

        API operation: POST /api/ListRolePolicies.
        """
        response = await self._client.api.list_role_policies.post(request)
        if response is None:
            raise RuntimeError("CAS ListRolePolicies returned no response body")
        return response



    async def aclose(self) -> None:
        if self._owns_http:
            await self._http_client.aclose()

    async def __aenter__(self) -> CasClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


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
    "ListUsersRequest",
    "ListUsersResponse",

    "RemoveRoleAssignmentRequest",

]

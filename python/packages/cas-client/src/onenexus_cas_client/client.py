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
from .generated.models.assume_s3_role_request import AssumeS3RoleRequest
from .generated.models.assume_s3_role_response import AssumeS3RoleResponse
from .generated.models.create_service_client_request import CreateServiceClientRequest
from .generated.models.create_service_client_response import CreateServiceClientResponse
from .generated.models.create_user_request import CreateUserRequest
from .generated.models.create_user_response import CreateUserResponse
from .generated.models.empty_s3_request import EmptyS3Request
from .generated.models.empty_service_client_request import EmptyServiceClientRequest
from .generated.models.list_s3_roles_response import ListS3RolesResponse
from .generated.models.list_service_clients_response import ListServiceClientsResponse


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
        response = await self._client.api.create_user.post(request)
        if response is None:
            raise RuntimeError("CAS CreateUser returned no response body")
        return response

    async def accept_invitation(
        self, request: AcceptInvitationRequest
    ) -> AcceptInvitationResponse:
        response = await self._client.api.accept_invitation.post(request)
        if response is None:
            raise RuntimeError("CAS AcceptInvitation returned no response body")
        return response

    async def list_s3_roles(self) -> ListS3RolesResponse:
        response = await self._client.api.list_s3_roles.post(EmptyS3Request())
        if response is None:
            raise RuntimeError("CAS ListS3Roles returned no response body")
        return response

    async def assume_s3_role(self, request: AssumeS3RoleRequest) -> AssumeS3RoleResponse:
        response = await self._client.api.assume_s3_role.post(request)
        if response is None:
            raise RuntimeError("CAS AssumeS3Role returned no response body")
        return response

    async def list_service_clients(self) -> ListServiceClientsResponse:
        response = await self._client.api.list_service_clients.post(EmptyServiceClientRequest())
        if response is None:
            raise RuntimeError("CAS ListServiceClients returned no response body")
        return response

    async def create_service_client(
        self, request: CreateServiceClientRequest
    ) -> CreateServiceClientResponse:
        response = await self._client.api.create_service_client.post(request)
        if response is None:
            raise RuntimeError("CAS CreateServiceClient returned no response body")
        return response

    async def add_service_client_key(
        self, request: AddServiceClientKeyRequest
    ) -> AddServiceClientKeyResponse:
        response = await self._client.api.add_service_client_key.post(request)
        if response is None:
            raise RuntimeError("CAS AddServiceClientKey returned no response body")
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
    "AssumeS3RoleRequest",
    "AssumeS3RoleResponse",
    "CasClient",
    "CreateServiceClientRequest",
    "CreateServiceClientResponse",
    "CreateUserRequest",
    "CreateUserResponse",
    "ListS3RolesResponse",
    "ListServiceClientsResponse",
]

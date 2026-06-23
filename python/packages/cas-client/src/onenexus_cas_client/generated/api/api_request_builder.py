from __future__ import annotations
from collections.abc import Callable
from kiota_abstractions.base_request_builder import BaseRequestBuilder
from kiota_abstractions.get_path_parameters import get_path_parameters
from kiota_abstractions.request_adapter import RequestAdapter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .accept_invitation.accept_invitation_request_builder import AcceptInvitationRequestBuilder
    from .add_service_client_key.add_service_client_key_request_builder import AddServiceClientKeyRequestBuilder
    from .assume_s3_role.assume_s3_role_request_builder import AssumeS3RoleRequestBuilder
    from .create_service_client.create_service_client_request_builder import CreateServiceClientRequestBuilder
    from .create_user.create_user_request_builder import CreateUserRequestBuilder
    from .list_s3_roles.list_s3_roles_request_builder import ListS3RolesRequestBuilder
    from .list_service_clients.list_service_clients_request_builder import ListServiceClientsRequestBuilder

class ApiRequestBuilder(BaseRequestBuilder):
    """
    Builds and executes requests for operations under /api
    """
    def __init__(self,request_adapter: RequestAdapter, path_parameters: Union[str, dict[str, Any]]) -> None:
        """
        Instantiates a new ApiRequestBuilder and sets the default values.
        param path_parameters: The raw url or the url-template parameters for the request.
        param request_adapter: The request adapter to use to execute the requests.
        Returns: None
        """
        super().__init__(request_adapter, "{+baseurl}/api", path_parameters)
    
    @property
    def accept_invitation(self) -> AcceptInvitationRequestBuilder:
        """
        The AcceptInvitation property
        """
        from .accept_invitation.accept_invitation_request_builder import AcceptInvitationRequestBuilder

        return AcceptInvitationRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def add_service_client_key(self) -> AddServiceClientKeyRequestBuilder:
        """
        The AddServiceClientKey property
        """
        from .add_service_client_key.add_service_client_key_request_builder import AddServiceClientKeyRequestBuilder

        return AddServiceClientKeyRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def assume_s3_role(self) -> AssumeS3RoleRequestBuilder:
        """
        The AssumeS3Role property
        """
        from .assume_s3_role.assume_s3_role_request_builder import AssumeS3RoleRequestBuilder

        return AssumeS3RoleRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def create_service_client(self) -> CreateServiceClientRequestBuilder:
        """
        The CreateServiceClient property
        """
        from .create_service_client.create_service_client_request_builder import CreateServiceClientRequestBuilder

        return CreateServiceClientRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def create_user(self) -> CreateUserRequestBuilder:
        """
        The CreateUser property
        """
        from .create_user.create_user_request_builder import CreateUserRequestBuilder

        return CreateUserRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def list_s3_roles(self) -> ListS3RolesRequestBuilder:
        """
        The ListS3Roles property
        """
        from .list_s3_roles.list_s3_roles_request_builder import ListS3RolesRequestBuilder

        return ListS3RolesRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def list_service_clients(self) -> ListServiceClientsRequestBuilder:
        """
        The ListServiceClients property
        """
        from .list_service_clients.list_service_clients_request_builder import ListServiceClientsRequestBuilder

        return ListServiceClientsRequestBuilder(self.request_adapter, self.path_parameters)
    


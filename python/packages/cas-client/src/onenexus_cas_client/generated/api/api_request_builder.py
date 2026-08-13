from __future__ import annotations
from collections.abc import Callable
from kiota_abstractions.base_request_builder import BaseRequestBuilder
from kiota_abstractions.get_path_parameters import get_path_parameters
from kiota_abstractions.request_adapter import RequestAdapter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .accept_invitation.accept_invitation_request_builder import AcceptInvitationRequestBuilder
    from .add_service_client_key.add_service_client_key_request_builder import AddServiceClientKeyRequestBuilder
    from .assign_role.assign_role_request_builder import AssignRoleRequestBuilder
    from .assume_s3_role.assume_s3_role_request_builder import AssumeS3RoleRequestBuilder
    from .attach_policy_to_role.attach_policy_to_role_request_builder import AttachPolicyToRoleRequestBuilder
    from .create_role.create_role_request_builder import CreateRoleRequestBuilder
    from .create_service_client.create_service_client_request_builder import CreateServiceClientRequestBuilder
    from .create_user.create_user_request_builder import CreateUserRequestBuilder
    from .delete_policy.delete_policy_request_builder import DeletePolicyRequestBuilder
    from .delete_role.delete_role_request_builder import DeleteRoleRequestBuilder
    from .detach_policy_from_role.detach_policy_from_role_request_builder import DetachPolicyFromRoleRequestBuilder
    from .disable_service_client.disable_service_client_request_builder import DisableServiceClientRequestBuilder
    from .get_policy.get_policy_request_builder import GetPolicyRequestBuilder
    from .list_policies.list_policies_request_builder import ListPoliciesRequestBuilder
    from .list_policy_attachments.list_policy_attachments_request_builder import ListPolicyAttachmentsRequestBuilder
    from .list_roles.list_roles_request_builder import ListRolesRequestBuilder
    from .list_role_assignments.list_role_assignments_request_builder import ListRoleAssignmentsRequestBuilder
    from .list_role_policies.list_role_policies_request_builder import ListRolePoliciesRequestBuilder
    from .list_s3_roles.list_s3_roles_request_builder import ListS3RolesRequestBuilder
    from .list_service_clients.list_service_clients_request_builder import ListServiceClientsRequestBuilder
    from .list_users.list_users_request_builder import ListUsersRequestBuilder
    from .publish_policy.publish_policy_request_builder import PublishPolicyRequestBuilder
    from .remove_role_assignment.remove_role_assignment_request_builder import RemoveRoleAssignmentRequestBuilder
    from .remove_service_client_key.remove_service_client_key_request_builder import RemoveServiceClientKeyRequestBuilder
    from .resend_user_invitation.resend_user_invitation_request_builder import ResendUserInvitationRequestBuilder
    from .update_policy.update_policy_request_builder import UpdatePolicyRequestBuilder

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
    def assign_role(self) -> AssignRoleRequestBuilder:
        """
        The AssignRole property
        """
        from .assign_role.assign_role_request_builder import AssignRoleRequestBuilder

        return AssignRoleRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def assume_s3_role(self) -> AssumeS3RoleRequestBuilder:
        """
        The AssumeS3Role property
        """
        from .assume_s3_role.assume_s3_role_request_builder import AssumeS3RoleRequestBuilder

        return AssumeS3RoleRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def attach_policy_to_role(self) -> AttachPolicyToRoleRequestBuilder:
        """
        The AttachPolicyToRole property
        """
        from .attach_policy_to_role.attach_policy_to_role_request_builder import AttachPolicyToRoleRequestBuilder

        return AttachPolicyToRoleRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def create_role(self) -> CreateRoleRequestBuilder:
        """
        The CreateRole property
        """
        from .create_role.create_role_request_builder import CreateRoleRequestBuilder

        return CreateRoleRequestBuilder(self.request_adapter, self.path_parameters)
    
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
    def delete_policy(self) -> DeletePolicyRequestBuilder:
        """
        The DeletePolicy property
        """
        from .delete_policy.delete_policy_request_builder import DeletePolicyRequestBuilder

        return DeletePolicyRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def delete_role(self) -> DeleteRoleRequestBuilder:
        """
        The DeleteRole property
        """
        from .delete_role.delete_role_request_builder import DeleteRoleRequestBuilder

        return DeleteRoleRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def detach_policy_from_role(self) -> DetachPolicyFromRoleRequestBuilder:
        """
        The DetachPolicyFromRole property
        """
        from .detach_policy_from_role.detach_policy_from_role_request_builder import DetachPolicyFromRoleRequestBuilder

        return DetachPolicyFromRoleRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def disable_service_client(self) -> DisableServiceClientRequestBuilder:
        """
        The DisableServiceClient property
        """
        from .disable_service_client.disable_service_client_request_builder import DisableServiceClientRequestBuilder

        return DisableServiceClientRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def get_policy(self) -> GetPolicyRequestBuilder:
        """
        The GetPolicy property
        """
        from .get_policy.get_policy_request_builder import GetPolicyRequestBuilder

        return GetPolicyRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def list_policies(self) -> ListPoliciesRequestBuilder:
        """
        The ListPolicies property
        """
        from .list_policies.list_policies_request_builder import ListPoliciesRequestBuilder

        return ListPoliciesRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def list_policy_attachments(self) -> ListPolicyAttachmentsRequestBuilder:
        """
        The ListPolicyAttachments property
        """
        from .list_policy_attachments.list_policy_attachments_request_builder import ListPolicyAttachmentsRequestBuilder

        return ListPolicyAttachmentsRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def list_role_assignments(self) -> ListRoleAssignmentsRequestBuilder:
        """
        The ListRoleAssignments property
        """
        from .list_role_assignments.list_role_assignments_request_builder import ListRoleAssignmentsRequestBuilder

        return ListRoleAssignmentsRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def list_role_policies(self) -> ListRolePoliciesRequestBuilder:
        """
        The ListRolePolicies property
        """
        from .list_role_policies.list_role_policies_request_builder import ListRolePoliciesRequestBuilder

        return ListRolePoliciesRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def list_roles(self) -> ListRolesRequestBuilder:
        """
        The ListRoles property
        """
        from .list_roles.list_roles_request_builder import ListRolesRequestBuilder

        return ListRolesRequestBuilder(self.request_adapter, self.path_parameters)
    
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
    
    @property
    def list_users(self) -> ListUsersRequestBuilder:
        """
        The ListUsers property
        """
        from .list_users.list_users_request_builder import ListUsersRequestBuilder

        return ListUsersRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def publish_policy(self) -> PublishPolicyRequestBuilder:
        """
        The PublishPolicy property
        """
        from .publish_policy.publish_policy_request_builder import PublishPolicyRequestBuilder

        return PublishPolicyRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def remove_role_assignment(self) -> RemoveRoleAssignmentRequestBuilder:
        """
        The RemoveRoleAssignment property
        """
        from .remove_role_assignment.remove_role_assignment_request_builder import RemoveRoleAssignmentRequestBuilder

        return RemoveRoleAssignmentRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def remove_service_client_key(self) -> RemoveServiceClientKeyRequestBuilder:
        """
        The RemoveServiceClientKey property
        """
        from .remove_service_client_key.remove_service_client_key_request_builder import RemoveServiceClientKeyRequestBuilder

        return RemoveServiceClientKeyRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def resend_user_invitation(self) -> ResendUserInvitationRequestBuilder:
        """
        The ResendUserInvitation property
        """
        from .resend_user_invitation.resend_user_invitation_request_builder import ResendUserInvitationRequestBuilder

        return ResendUserInvitationRequestBuilder(self.request_adapter, self.path_parameters)
    
    @property
    def update_policy(self) -> UpdatePolicyRequestBuilder:
        """
        The UpdatePolicy property
        """
        from .update_policy.update_policy_request_builder import UpdatePolicyRequestBuilder

        return UpdatePolicyRequestBuilder(self.request_adapter, self.path_parameters)
    


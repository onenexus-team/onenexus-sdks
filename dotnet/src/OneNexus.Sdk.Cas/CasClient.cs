using System;
using System.Threading;
using System.Threading.Tasks;
using OneNexus.Sdk.Cas.Models;
using OneNexus.Sdk.Core;

namespace OneNexus.Sdk.Cas;

/// <summary>Typed operations for the CAS customer API.</summary>
public sealed class CasClient : IDisposable
{
    private readonly ServiceTransport _transport;
    private readonly CasGeneratedClient _api;
    private readonly ServiceTransport.TokenRoute _s3Route;

    /// <summary>Connects to a CAS service with application-provided credentials.</summary>
    public CasClient(Uri baseUrl, IAccessTokenCredential credentials, SdkClientOptions? options = null)
    {
        _transport = new ServiceTransport(baseUrl, credentials, options);
        _api = new CasGeneratedClient(_transport.Adapter);
        _s3Route = new ServiceTransport.TokenRoute(token => CasRouting.ResolveAssumeS3RoleBaseUrl(baseUrl, token));
    }

    /// <summary>Updates selected profile fields for the current human user.</summary>
    public Task<UpdateProfileResponse> UpdateProfileAsync(UpdateProfileRequest request, CancellationToken cancellationToken = default) =>
        UpdateProfileAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Updates selected profile fields for the current human user.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<UpdateProfileResponse> UpdateProfileAsync(UpdateProfileRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Account.Profile.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Lists the tenants the signed-in person can use, for the console's tenant switcher.</summary>
    public Task<ListMyTenantsResponse> ListMyTenantsAsync(CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListMyTenants.PostAsync(new ListMyTenantsRequest(), cancellationToken: cancellationToken));

    /// <summary>Idempotently assigns one role to a user or service client.</summary>
    public Task<AssignRoleResponse> AssignRoleAsync(AssignRoleRequest request, CancellationToken cancellationToken = default) =>
        AssignRoleAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Idempotently assigns one role to a user or service client.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<AssignRoleResponse> AssignRoleAsync(AssignRoleRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.AssignRole.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Removes one direct role assignment using its current state token.</summary>
    public Task<AuthorizationRelationshipRemovedResponse> RemoveRoleAssignmentAsync(RemoveRoleAssignmentRequest request, CancellationToken cancellationToken = default) =>
        RemoveRoleAssignmentAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Removes one direct role assignment using its current state token.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<AuthorizationRelationshipRemovedResponse> RemoveRoleAssignmentAsync(RemoveRoleAssignmentRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.RemoveRoleAssignment.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Lists direct assignments by exactly one role or assignee filter.</summary>
    public Task<ListRoleAssignmentsResponse> ListRoleAssignmentsAsync(ListRoleAssignmentsRequest? request = null, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListRoleAssignments.PostAsync(request ?? new ListRoleAssignmentsRequest(), cancellationToken: cancellationToken));

    /// <summary>Compiles and idempotently attaches one tenant- or platform-managed policy to a role.</summary>
    public Task<AttachPolicyToRoleResponse> AttachPolicyToRoleAsync(AttachPolicyToRoleRequest request, CancellationToken cancellationToken = default) =>
        AttachPolicyToRoleAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Compiles and idempotently attaches one tenant- or platform-managed policy to a role.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<AttachPolicyToRoleResponse> AttachPolicyToRoleAsync(AttachPolicyToRoleRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.AttachPolicyToRole.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Detaches one policy from one role using the relationship state token.</summary>
    public Task<AuthorizationRelationshipRemovedResponse> DetachPolicyFromRoleAsync(DetachPolicyFromRoleRequest request, CancellationToken cancellationToken = default) =>
        DetachPolicyFromRoleAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Detaches one policy from one role using the relationship state token.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<AuthorizationRelationshipRemovedResponse> DetachPolicyFromRoleAsync(DetachPolicyFromRoleRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.DetachPolicyFromRole.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Lists roles to which one policy is directly attached.</summary>
    public Task<ListPolicyAttachmentsResponse> ListPolicyAttachmentsAsync(ListPolicyAttachmentsRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListPolicyAttachments.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Lists tenant- and platform-managed policies directly attached to one role.</summary>
    public Task<ListPolicyAttachmentsResponse> ListRolePoliciesAsync(ListRolePoliciesRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListRolePolicies.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Validates and publishes new tenant-managed policy content.</summary>
    public Task<PublishPolicyResponse> PublishPolicyAsync(PublishPolicyRequest request, CancellationToken cancellationToken = default) =>
        PublishPolicyAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Validates and publishes new tenant-managed policy content.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<PublishPolicyResponse> PublishPolicyAsync(PublishPolicyRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.PublishPolicy.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Lists one page of policies visible to the caller's tenant.</summary>
    public Task<ListPoliciesResponse> ListPoliciesAsync(ListPoliciesRequest? request = null, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListPolicies.PostAsync(request ?? new ListPoliciesRequest(), cancellationToken: cancellationToken));

    /// <summary>Gets one policy's content without its role attachments.</summary>
    public Task<GetPolicyResponse> GetPolicyAsync(GetPolicyRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.GetPolicy.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Updates only the content of an existing tenant-managed policy.</summary>
    public Task<UpdatePolicyResponse> UpdatePolicyAsync(UpdatePolicyRequest request, CancellationToken cancellationToken = default) =>
        UpdatePolicyAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Updates only the content of an existing tenant-managed policy.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<UpdatePolicyResponse> UpdatePolicyAsync(UpdatePolicyRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.UpdatePolicy.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Deletes one unattached tenant-managed policy.</summary>
    public Task<DeletePolicyResponse> DeletePolicyAsync(DeletePolicyRequest request, CancellationToken cancellationToken = default) =>
        DeletePolicyAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Deletes one unattached tenant-managed policy.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<DeletePolicyResponse> DeletePolicyAsync(DeletePolicyRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.DeletePolicy.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Deletes one unreferenced tenant authorization role.</summary>
    public Task<DeleteAuthorizationRoleResponse> DeleteRoleAsync(DeleteAuthorizationRoleRequest request, CancellationToken cancellationToken = default) =>
        DeleteRoleAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Deletes one unreferenced tenant authorization role.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<DeleteAuthorizationRoleResponse> DeleteRoleAsync(DeleteAuthorizationRoleRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.DeleteRole.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Idempotently creates one tenant authorization role.</summary>
    public Task<CreateAuthorizationRoleResponse> CreateRoleAsync(CreateAuthorizationRoleRequest request, CancellationToken cancellationToken = default) =>
        CreateRoleAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Idempotently creates one tenant authorization role.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<CreateAuthorizationRoleResponse> CreateRoleAsync(CreateAuthorizationRoleRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.CreateRole.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Updates the optional human-readable description of one tenant role.</summary>
    public Task<UpdateAuthorizationRoleDescriptionResponse> UpdateRoleDescriptionAsync(UpdateAuthorizationRoleDescriptionRequest request, CancellationToken cancellationToken = default) =>
        UpdateRoleDescriptionAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Updates the optional human-readable description of one tenant role.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<UpdateAuthorizationRoleDescriptionResponse> UpdateRoleDescriptionAsync(UpdateAuthorizationRoleDescriptionRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.UpdateRoleDescription.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Lists authorization roles in the caller's tenant.</summary>
    public Task<ListAuthorizationRolesResponse> ListRolesAsync(ListAuthorizationRolesRequest? request = null, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListRoles.PostAsync(request ?? new ListAuthorizationRolesRequest(), cancellationToken: cancellationToken));

    /// <summary>List the S3 IAM roles provisioned in the caller's tenant account.</summary>
    public Task<ListS3RolesResponse> ListS3RolesAsync(CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListS3Roles.PostAsync(new EmptyS3Request(), cancellationToken: cancellationToken));

    /// <summary>Assume an S3 role in the caller's tenant account and return temporary credentials.</summary>
    public Task<AssumeS3RoleResponse> AssumeS3RoleAsync(AssumeS3RoleRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.AssumeS3Role.PostAsync(request, config => config.Options.Add(_s3Route), cancellationToken));

    /// <summary>List OAuth service clients owned by the caller's tenant.</summary>
    public Task<ListServiceClientsResponse> ListServiceClientsAsync(CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListServiceClients.PostAsync(new EmptyServiceClientRequest(), cancellationToken: cancellationToken));

    /// <summary>Create a tenant-owned service client with its first browser-generated public assertion key.</summary>
    public Task<CreateServiceClientResponse> CreateServiceClientAsync(CreateServiceClientRequest request, CancellationToken cancellationToken = default) =>
        CreateServiceClientAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Create a tenant-owned service client with its first browser-generated public assertion key.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<CreateServiceClientResponse> CreateServiceClientAsync(CreateServiceClientRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.CreateServiceClient.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Add an additional public assertion key to a service client.</summary>
    public Task<AddServiceClientKeyResponse> AddServiceClientKeyAsync(AddServiceClientKeyRequest request, CancellationToken cancellationToken = default) =>
        AddServiceClientKeyAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Add an additional public assertion key to a service client.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<AddServiceClientKeyResponse> AddServiceClientKeyAsync(AddServiceClientKeyRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.AddServiceClientKey.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Revokes one public assertion key from a service client.</summary>
    public Task<RemoveServiceClientKeyResponse> RemoveServiceClientKeyAsync(RemoveServiceClientKeyRequest request, CancellationToken cancellationToken = default) =>
        RemoveServiceClientKeyAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Revokes one public assertion key from a service client.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<RemoveServiceClientKeyResponse> RemoveServiceClientKeyAsync(RemoveServiceClientKeyRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.RemoveServiceClientKey.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Disables a service client so it cannot obtain new access tokens.</summary>
    public Task<DisableServiceClientResponse> DisableServiceClientAsync(DisableServiceClientRequest request, CancellationToken cancellationToken = default) =>
        DisableServiceClientAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Disables a service client so it cannot obtain new access tokens.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<DisableServiceClientResponse> DisableServiceClientAsync(DisableServiceClientRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.DisableServiceClient.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Admin invites a user into their own tenant and triggers the invite email.</summary>
    public Task<CreateUserResponse> CreateUserAsync(CreateUserRequest request, CancellationToken cancellationToken = default) =>
        CreateUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Admin invites a user into their own tenant and triggers the invite email.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<CreateUserResponse> CreateUserAsync(CreateUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.CreateUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Re-sends an invitation to a pending member in the caller's tenant.</summary>
    public Task ResendUserInvitationAsync(ResendUserInvitationRequest request, CancellationToken cancellationToken = default) =>
        ResendUserInvitationAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Re-sends an invitation to a pending member in the caller's tenant.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task ResendUserInvitationAsync(ResendUserInvitationRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        _api.Api.ResendUserInvitation.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken);

    /// <summary>Lists users in the authenticated caller's own tenant.</summary>
    public Task<ListUsersResponse> ListUsersAsync(ListUsersRequest? request = null, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.ListUsers.PostAsync(request ?? new ListUsersRequest(), cancellationToken: cancellationToken));

    /// <summary>Suspends an active member in the authenticated caller's tenant.</summary>
    public Task<SuspendUserResponse> SuspendUserAsync(SuspendUserRequest request, CancellationToken cancellationToken = default) =>
        SuspendUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Suspends an active member in the authenticated caller's tenant.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<SuspendUserResponse> SuspendUserAsync(SuspendUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.SuspendUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Restores a suspended member in the authenticated caller's tenant.</summary>
    public Task<UnsuspendUserResponse> UnsuspendUserAsync(UnsuspendUserRequest request, CancellationToken cancellationToken = default) =>
        UnsuspendUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Restores a suspended member in the authenticated caller's tenant.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<UnsuspendUserResponse> UnsuspendUserAsync(UnsuspendUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.Api.UnsuspendUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Removes a member from the authenticated caller's tenant for good.</summary>
    public Task RemoveUserAsync(RemoveUserRequest request, CancellationToken cancellationToken = default) =>
        RemoveUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Removes a member from the authenticated caller's tenant for good.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task RemoveUserAsync(RemoveUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        _api.Api.RemoveUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken);

    /// <summary>Releases the SDK transport. An injected HTTP client remains caller-owned.</summary>
    public void Dispose() => _transport.Dispose();
}

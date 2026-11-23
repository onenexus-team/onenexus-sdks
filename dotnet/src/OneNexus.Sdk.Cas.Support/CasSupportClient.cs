using System;
using System.Threading;
using System.Threading.Tasks;
using OneNexus.Sdk.Cas.Support.Models;
using OneNexus.Sdk.Core;

namespace OneNexus.Sdk.Cas.Support;

/// <summary>Typed operations for the CAS support API.</summary>
public sealed class CasSupportClient : IDisposable
{
    private readonly ServiceTransport _transport;
    private readonly CasSupportGeneratedClient _api;

    /// <summary>Connects to a CAS service with application-provided credentials.</summary>
    public CasSupportClient(Uri baseUrl, IAccessTokenCredential credentials, SdkClientOptions? options = null)
    {
        _transport = new ServiceTransport(baseUrl, credentials, options);
        _api = new CasSupportGeneratedClient(_transport.Adapter);
    }

    /// <summary>Describe the first-party default S3 account and whether it has been provisioned yet.</summary>
    public Task<S3DefaultAccountResponse> GetS3DefaultAccountAsync(CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.GetS3DefaultAccount.PostAsync(new EmptyS3Request(), cancellationToken: cancellationToken));

    /// <summary>Provision the first-party default S3 account and its account-root user.</summary>
    public Task<ProvisionS3DefaultAccountResponse> ProvisionS3DefaultAccountAsync(CancellationToken cancellationToken = default) =>
        ProvisionS3DefaultAccountAsync(idempotencyKey: null, cancellationToken);

    /// <summary>Provision the first-party default S3 account and its account-root user.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<ProvisionS3DefaultAccountResponse> ProvisionS3DefaultAccountAsync(string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.ProvisionS3DefaultAccount.PostAsync(new EmptyS3Request(), ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>List every RGW account known to the cluster.</summary>
    public Task<ListS3AccountsResponse> ListS3AccountsAsync(CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.ListS3Accounts.PostAsync(new EmptyS3Request(), cancellationToken: cancellationToken));

    /// <summary>Finds the account that has an address.</summary>
    public Task<DescribeAccountResponse> DescribeAccountAsync(DescribeAccountRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.DescribeAccount.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Deletes a person's account once none of its users is live.</summary>
    public Task DeleteAccountAsync(DeleteAccountRequest request, CancellationToken cancellationToken = default) =>
        DeleteAccountAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Deletes a person's account once none of its users is live.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task DeleteAccountAsync(DeleteAccountRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        _api.SupportApi.DeleteAccount.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken);

    /// <summary>Evaluates one principal/action/resource tuple exactly as the owning service's PEP would, without performing the operation itself.</summary>
    public Task<EvaluateAuthorizationResponse> EvaluateAuthorizationAsync(EvaluateAuthorizationRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.EvaluateAuthorization.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Create a new tenant.</summary>
    public Task<CreateTenantResponse> CreateTenantAsync(CreateTenantRequest request, CancellationToken cancellationToken = default) =>
        CreateTenantAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Create a new tenant.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<CreateTenantResponse> CreateTenantAsync(CreateTenantRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.CreateTenant.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Look up a tenant by Guid PK.</summary>
    public Task<DescribeTenantResponse> DescribeTenantAsync(DescribeTenantRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.DescribeTenant.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Page across all tenants known to CAS.</summary>
    public Task<ListTenantsResponse> ListTenantsAsync(ListTenantsRequest? request = null, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.ListTenants.PostAsync(request ?? new ListTenantsRequest(), cancellationToken: cancellationToken));

    /// <summary>Page across the users belonging to a specific tenant.</summary>
    public Task<ListTenantUsersResponse> ListTenantUsersAsync(ListTenantUsersRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.ListTenantUsers.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Searches the users of every tenant by name or email.</summary>
    public Task<SearchUsersResponse> SearchUsersAsync(SearchUsersRequest request, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.SearchUsers.PostAsync(request, cancellationToken: cancellationToken));

    /// <summary>Add a roleless user to an existing active tenant.</summary>
    public Task<CreateUserResponse> AddTenantUserAsync(AddTenantUserRequest request, CancellationToken cancellationToken = default) =>
        AddTenantUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Add a roleless user to an existing active tenant.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<CreateUserResponse> AddTenantUserAsync(AddTenantUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.AddTenantUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Re-sends the invitation email for an existing pending user.</summary>
    public Task<ResendInvitationResponse> ResendInvitationAsync(ResendInvitationRequest request, CancellationToken cancellationToken = default) =>
        ResendInvitationAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Re-sends the invitation email for an existing pending user.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<ResendInvitationResponse> ResendInvitationAsync(ResendInvitationRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.ResendInvitation.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Suspends a tenant, preventing normal sign-in and onboarding traffic.</summary>
    public Task<SuspendTenantResponse> SuspendTenantAsync(SuspendTenantRequest request, CancellationToken cancellationToken = default) =>
        SuspendTenantAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Suspends a tenant, preventing normal sign-in and onboarding traffic.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<SuspendTenantResponse> SuspendTenantAsync(SuspendTenantRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.SuspendTenant.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Re-activates a suspended tenant.</summary>
    public Task<UnsuspendTenantResponse> UnsuspendTenantAsync(UnsuspendTenantRequest request, CancellationToken cancellationToken = default) =>
        UnsuspendTenantAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Re-activates a suspended tenant.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<UnsuspendTenantResponse> UnsuspendTenantAsync(UnsuspendTenantRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.UnsuspendTenant.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Suspends an active user.</summary>
    public Task<SuspendTenantUserResponse> SuspendTenantUserAsync(SuspendTenantUserRequest request, CancellationToken cancellationToken = default) =>
        SuspendTenantUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Suspends an active user.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<SuspendTenantUserResponse> SuspendTenantUserAsync(SuspendTenantUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.SuspendTenantUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Re-activates a suspended user with the role assignments they had before suspension.</summary>
    public Task<UnsuspendTenantUserResponse> UnsuspendTenantUserAsync(UnsuspendTenantUserRequest request, CancellationToken cancellationToken = default) =>
        UnsuspendTenantUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Re-activates a suspended user with the role assignments they had before suspension.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task<UnsuspendTenantUserResponse> UnsuspendTenantUserAsync(UnsuspendTenantUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        ServiceTransport.RequiredAsync(
            _api.SupportApi.UnsuspendTenantUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken));

    /// <summary>Removes a user of any tenant for good.</summary>
    public Task RemoveTenantUserAsync(RemoveTenantUserRequest request, CancellationToken cancellationToken = default) =>
        RemoveTenantUserAsync(request, idempotencyKey: null, cancellationToken);

    /// <summary>Removes a user of any tenant for good.</summary>
    /// <remarks>Supply the same key when repeating this logical request after a timeout.</remarks>
    public Task RemoveTenantUserAsync(RemoveTenantUserRequest request, string? idempotencyKey, CancellationToken cancellationToken = default) =>
        _api.SupportApi.RemoveTenantUser.PostAsync(request, ServiceTransport.WithIdempotencyKey(idempotencyKey), cancellationToken);

    /// <summary>Releases the SDK transport. An injected HTTP client remains caller-owned.</summary>
    public void Dispose() => _transport.Dispose();
}

import {
    ClientBase,
    type ClientBaseConfig,
    type ClientRequestOptions,
} from '@onenexus-team/sdk-core';

import type {
    AddTenantUserRequest,
    CreateTenantRequest,
    CreateTenantResponse,
    CreateUserResponse,
    DescribeTenantRequest,
    DescribeTenantResponse,
    EmptyS3Request,
    EvaluateAuthorizationRequest,
    EvaluateAuthorizationResponse,
    ListS3AccountsResponse,
    ListTenantsRequest,
    ListTenantsResponse,
    ListTenantUsersRequest,
    ListTenantUsersResponse,
    ProvisionS3DefaultAccountResponse,
    ResendInvitationRequest,
    ResendInvitationResponse,
    S3DefaultAccountResponse,
    SuspendTenantRequest,
    SuspendTenantResponse,
    UnsuspendTenantRequest,
    UnsuspendTenantResponse,
} from './generated/models/index.js';
import {
    createCasSupportApiClient,
    type CasSupportApiClient,
} from './generated/casSupportApiClient.js';

/**
 * Shared empty request body for the parameterless S3 administration RPCs.
 * The endpoints still post a JSON object; this is the canonical `{}` payload.
 */
const EMPTY_S3_REQUEST: EmptyS3Request = {};

/**
 * Construction-time configuration for {@link CasSupportClient}.
 *
 * `baseUrl` is the CAS service host (e.g. `https://cas.acme.com`); the client
 * appends `/support-api/...` paths against it at request time. `credentials`
 * provides `Authorization` headers for every request. `issuer` for the
 * underlying credential is configured separately, on the credential itself.
 *
 * Retry settings (`retry.limit`, `retry.backoffLimitMs`) and credential refresh
 * leeway (`refreshLeewayMs`) are inherited from {@link ClientBaseConfig}.
 */
export type CasSupportClientConfig = ClientBaseConfig;

/**
 * Per-call options accepted by every {@link CasSupportClient} method.
 *
 * Today the only field is `signal` for cancellation; the type is named and
 * exported so future per-call overrides (custom headers, request-id, etc.)
 * can be added without changing every method signature.
 */
export type CasSupportRequestOptions = ClientRequestOptions;

type NumericLimitRequest<T extends { limit?: unknown }> = Omit<T, 'limit'> & {
    readonly limit?: T['limit'] | number | string;
};
type EvaluateAuthorizationFacadeRequest = Omit<EvaluateAuthorizationRequest, 'context'> & {
    readonly context?: unknown;
};

/**
 * Typed client for the Central Auth Service Support API `/support-api/*` RPC
 * surface.
 *
 * This is the support-team operations surface — distinct from the regular CAS
 * client (`@onenexus-team/cas-client`, `/api/*`). It is generated from a separate
 * OpenAPI spec (`specs/cas-support/openapi.json`) and shares the same
 * transport, credential, and error primitives from `@onenexus-team/sdk-core`.
 *
 * Each method is a thin binding around a Kiota-generated request builder. The
 * client inherits {@link ClientBase}'s request adapter, credentials, native
 * retry policy, timeout behavior, and skew-aware client context.
 * Construction is cheap; instantiate one per CAS deployment (typically once
 * per process), or per logical caller when an application needs to talk to CAS
 * under multiple identities.
 *
 * Method names follow the OpenAPI operation IDs. The generated functions are
 * already RPC-shaped (for example `createTenant`), and these wrappers keep the
 * public surface flat while hiding internal transport options from consumers.
 *
 * @example
 * ```ts
 * import { CasSupportClient } from '@onenexus-team/cas-support-client';
 * import { TokenGrantCredentials } from '@onenexus-team/sdk-core';
 *
 * const support = new CasSupportClient({
 *     baseUrl: 'https://cas.acme.com',
 *     credentials: new TokenGrantCredentials({
 *         token: {
 *             accessToken: '...',
 *             tokenType: 'Bearer',
 *             expiresAt: new Date(Date.now() + 60 * 60 * 1000),
 *         },
 *     }),
 * });
 *
 * const tenant = await support.createTenant({
 *     tenantSlug: 'tn_acme',
 *     displayName: 'Acme Inc',
 *     rootEmail: 'admin@acme.com',
 *     rootDisplayName: 'Acme Admin',
 *     clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
 * });
 * ```
 */
export class CasSupportClient extends ClientBase {
    private readonly kiota: CasSupportApiClient;

    constructor(config: CasSupportClientConfig) {
        super(config);
        this.kiota = createCasSupportApiClient(this.requestAdapter);
    }

    // -- Tenant management ---------------------------------------------------

    /**
     * Create a new tenant.
     *
     * @see POST /support-api/CreateTenant
     */
    createTenant = (
        req: CreateTenantRequest,
        options?: CasSupportRequestOptions,
    ): Promise<CreateTenantResponse> =>
        this.expectResponse(
            this.kiota.supportApi.createTenant.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Look up a tenant by Guid PK.
     *
     * @see POST /support-api/DescribeTenant
     */
    describeTenant = (
        req: DescribeTenantRequest,
        options?: CasSupportRequestOptions,
    ): Promise<DescribeTenantResponse> =>
        this.expectResponse(
            this.kiota.supportApi.describeTenant.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Page across all tenants known to CAS. Platform-admin / support surface — there is no tenant
     * scoping, this returns rows for every tenant the caller is authorized to see.
     *
     * Ordering + pagination. Bidirectional cursor pagination on the Tenant.Id UUID v7 PK. Forward
     * (after) and backward (before) directions both resolve to an index range scan on the PK b-tree
     * with no OFFSET cost. Items are always returned in tenantId ascending order regardless of
     * direction — backward pages are reversed server-side. Because the PK is UUID v7 (time-ordered),
     * this is also a chronological listing for free. Authorization. The class-level PlatformSupport
     * policy requires an active administrator of the reserved OneNexus platform tenant. CAS resolves
     * this from the current authorization store, so a token does not retain access after an
     * administrator role is removed.
     *
     * @see POST /support-api/ListTenants
     */
    listTenants = (
        req: NumericLimitRequest<ListTenantsRequest>,
        options?: CasSupportRequestOptions,
    ): Promise<ListTenantsResponse> =>
        this.expectResponse(
            this.kiota.supportApi.listTenants.post(
                req as ListTenantsRequest,
                this.requestConfiguration(req, options),
            ),
        );

    /**
     * Page across the users belonging to a specific tenant. Platform-admin / support surface — the
     * target tenant is identified by Guid in the request body, not inferred from the caller's
     * principal.
     *
     * Ordering + pagination. Same shape as Task&lt;IActionResult&gt;
     * TenantController.ListTenants(ListTenantsRequest request, CancellationToken cancellationToken)
     * but on the Users table, filtered to a single tenant. The WHERE TenantId = ? AND Id &gt; ?
     * predicate rides the leading column of the composite IX_Users_TenantId_NormalizedEmail index for
     * the tenant filter and the PK for the cursor bound. Tenant status is NOT a precondition. Listing
     * the users of a suspended or soft-deleted tenant is a legitimate operator use case (audit,
     * cleanup, recovery). Only a missing tenant returns 404; a tenant that exists but is non-active
     * still serves its user list. Authorization. The class-level PlatformSupport policy requires an
     * active administrator of the reserved OneNexus platform tenant. CAS resolves this from the
     * current authorization store, so a token does not retain access after an administrator role is
     * removed.
     *
     * @see POST /support-api/ListTenantUsers
     */
    listTenantUsers = (
        req: NumericLimitRequest<ListTenantUsersRequest>,
        options?: CasSupportRequestOptions,
    ): Promise<ListTenantUsersResponse> =>
        this.expectResponse(
            this.kiota.supportApi.listTenantUsers.post(
                req as ListTenantUsersRequest,
                this.requestConfiguration(req, options),
            ),
        );

    /**
     * Add a roleless user to an existing active tenant. Role grants are separate authorization-
     * administration operations.
     *
     * Authorization. The caller must be an active human TenantAdmin of the reserved platform tenant.
     * This is the implemented operator gate until a distinct platform_admin authorization contract
     * exists. Differs from TenantUserController.CreateUser in that the target tenant comes from the
     * request body, not the caller's principal. The downstream invitation logic is identical and runs
     * through IInvitationService.
     *
     * @see POST /support-api/AddTenantUser
     */
    addTenantUser = (
        req: AddTenantUserRequest,
        options?: CasSupportRequestOptions,
    ): Promise<CreateUserResponse> =>
        this.expectResponse(
            this.kiota.supportApi.addTenantUser.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Re-sends the invitation email for an existing pending user.
     *
     * @see POST /support-api/ResendInvitation
     */
    resendInvitation = (
        req: ResendInvitationRequest,
        options?: CasSupportRequestOptions,
    ): Promise<ResendInvitationResponse> =>
        this.expectResponse(
            this.kiota.supportApi.resendInvitation.post(
                req,
                this.requestConfiguration(req, options),
            ),
        );

    /**
     * Suspends a tenant, preventing normal sign-in and onboarding traffic.
     *
     * @see POST /support-api/SuspendTenant
     */
    suspendTenant = (
        req: SuspendTenantRequest,
        options?: CasSupportRequestOptions,
    ): Promise<SuspendTenantResponse> =>
        this.expectResponse(
            this.kiota.supportApi.suspendTenant.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Re-activates a suspended tenant.
     *
     * @see POST /support-api/UnsuspendTenant
     */
    unsuspendTenant = (
        req: UnsuspendTenantRequest,
        options?: CasSupportRequestOptions,
    ): Promise<UnsuspendTenantResponse> =>
        this.expectResponse(
            this.kiota.supportApi.unsuspendTenant.post(
                req,
                this.requestConfiguration(req, options),
            ),
        );

    // -- Authorization diagnostics -----------------------------------------

    /**
     * Evaluates one principal/action/resource tuple exactly as the owning service's PEP would, without
     * performing the operation itself.
     *
     * @see POST /support-api/EvaluateAuthorization
     */
    evaluateAuthorization = (
        req: EvaluateAuthorizationFacadeRequest,
        options?: CasSupportRequestOptions,
    ): Promise<EvaluateAuthorizationResponse> =>
        this.expectResponse(
            this.kiota.supportApi.evaluateAuthorization.post(
                req as EvaluateAuthorizationRequest,
                this.requestConfiguration(req, options),
            ),
        );

    // -- Ceph S3 administration ---------------------------------------------

    /**
     * Describe the first-party default S3 account and whether it has been provisioned yet.
     *
     * @see POST /support-api/GetS3DefaultAccount
     */
    getS3DefaultAccount = (options?: CasSupportRequestOptions): Promise<S3DefaultAccountResponse> =>
        this.expectResponse(
            this.kiota.supportApi.getS3DefaultAccount.post(
                EMPTY_S3_REQUEST,
                this.requestConfiguration(EMPTY_S3_REQUEST, options),
            ),
        );

    /**
     * Provision the first-party default S3 account and its account-root user. Idempotent on the
     * account: if it already exists the existing account is returned and the root user is not
     * (re)created.
     *
     * @see POST /support-api/ProvisionS3DefaultAccount
     */
    provisionS3DefaultAccount = (
        options?: CasSupportRequestOptions,
    ): Promise<ProvisionS3DefaultAccountResponse> =>
        this.expectResponse(
            this.kiota.supportApi.provisionS3DefaultAccount.post(
                EMPTY_S3_REQUEST,
                this.requestConfiguration(EMPTY_S3_REQUEST, options),
            ),
        );

    /**
     * List every RGW account known to the cluster.
     *
     * @see POST /support-api/ListS3Accounts
     */
    listS3Accounts = (options?: CasSupportRequestOptions): Promise<ListS3AccountsResponse> =>
        this.expectResponse(
            this.kiota.supportApi.listS3Accounts.post(
                EMPTY_S3_REQUEST,
                this.requestConfiguration(EMPTY_S3_REQUEST, options),
            ),
        );
}

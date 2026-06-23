import { ClientBase, type ClientBaseConfig } from '@onenexus-team/sdk-core';

import type {
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    AddServiceClientKeyRequest,
    AddServiceClientKeyResponse,
    AssumeS3RoleRequest,
    AssumeS3RoleResponse,
    CreateServiceClientRequest,
    CreateServiceClientResponse,
    CreateUserRequest,
    CreateUserResponse,
    EmptyS3Request,
    ListS3RolesResponse,
    ListServiceClientsResponse,
} from './generated/schemas/index.js';
import { getTenantServiceClient } from './generated/tenant-service-client/tenant-service-client.js';
import { getTenantS3 } from './generated/tenant-s3/tenant-s3.js';
import { getTenantUser } from './generated/tenant-user/tenant-user.js';
import type { PlatformMutatorOptions } from './mutator.js';

/**
 * Construction-time configuration for {@link CasClient}.
 *
 * `baseUrl` is the CAS service host (e.g. `https://cas.acme.com`); the client
 * appends `/api/...` paths against it at request time. `credentials` provides
 * `Authorization` headers for every request. `issuer` for the
 * underlying credential is configured separately, on the credential itself.
 *
 * Retry settings (`retry.limit`, `retry.backoffLimitMs`) and credential refresh
 * leeway (`refreshLeewayMs`) are inherited from {@link ClientBaseConfig}.
 */
export interface CasClientConfig extends ClientBaseConfig {}

/**
 * Per-call options accepted by every {@link CasClient} method.
 *
 * Today the only field is `signal` for cancellation; the type is named and
 * exported so future per-call overrides (custom headers, request-id, etc.)
 * can be added without changing every method signature.
 */
export type CasRequestOptions = Omit<PlatformMutatorOptions, 'http'>;

/**
 * Typed client for the Central Auth Service Customer API `/api/*` RPC surface.
 *
 * This is the customer-facing user surface (`CreateUser`, `AcceptInvitation`).
 * Tenant-management and support operations live in a separate spec and are
 * served by `@onenexus-team/cas-support-client` (`/support-api/*`).
 *
 * Each method is a thin binding around an orval-generated function: the client
 * inherits {@link ClientBase}'s Ky transport, credentials, retry policy, and
 * client context, then passes the transport through to the mutator via the
 * second-argument options slot.
 * Construction is cheap; instantiate one per CAS deployment (typically once
 * per process), or per logical caller when an application needs to talk to CAS
 * under multiple identities (e.g. an admin background job alongside a
 * user-acting BFF request).
 *
 * Method names follow the OpenAPI operation IDs. The generated functions are
 * already RPC-shaped (for example `createUser`), and these wrappers keep the
 * public surface flat while hiding internal transport options from consumers.
 *
 * @example
 * ```ts
 * import { CasClient } from '@onenexus-team/cas-client';
 * import { TokenGrantCredentials } from '@onenexus-team/sdk-core';
 *
 * const cas = new CasClient({
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
 * const user = await cas.createUser({
 *     tenantId: 'tn_acme',
 *     email: 'a@b.c',
 *     displayName: 'A B',
 *     clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
 * });
 * ```
 */
export class CasClient extends ClientBase {
    private readonly tenantUser: ReturnType<typeof getTenantUser>;
    private readonly tenantS3: ReturnType<typeof getTenantS3>;
    private readonly tenantServiceClient: ReturnType<typeof getTenantServiceClient>;

    constructor(config: CasClientConfig) {
        super(config);
        this.tenantUser = getTenantUser();
        this.tenantS3 = getTenantS3();
        this.tenantServiceClient = getTenantServiceClient();
    }

    // -- Tenant user management ----------------------------------------------

    createUser = (
        req: CreateUserRequest,
        options?: CasRequestOptions,
    ): Promise<CreateUserResponse> => this.tenantUser.createUser(req, this.mutatorOptions(options));

    acceptInvitation = (
        req: AcceptInvitationRequest,
        options?: CasRequestOptions,
    ): Promise<AcceptInvitationResponse> =>
        this.tenantUser.acceptInvitation(req, this.mutatorOptions(options));

    // -- Tenant S3 -----------------------------------------------------------

    /**
     * List the S3 IAM roles provisioned in the caller's tenant account.
     * (`POST /api/ListS3Roles`).
     */
    listS3Roles = (options?: CasRequestOptions): Promise<ListS3RolesResponse> =>
        this.tenantS3.listS3Roles({}, this.mutatorOptions(options));

    /**
     * Assume a role in the caller's tenant account. CAS authorizes the user
     * and signs the RGW STS AssumeRole call with tenant-root credentials,
     * returning temporary S3 credentials. (`POST /api/AssumeS3Role`).
     */
    assumeS3Role = (
        req: AssumeS3RoleRequest,
        options?: CasRequestOptions,
    ): Promise<AssumeS3RoleResponse> =>
        this.tenantS3.assumeS3Role(req, this.mutatorOptions(options));

    // -- Tenant service clients --------------------------------------------

    /**
     * List OAuth service clients owned by the caller's tenant.
     * (`POST /api/ListServiceClients`).
     */
    listServiceClients = (options?: CasRequestOptions): Promise<ListServiceClientsResponse> =>
        this.tenantServiceClient.listServiceClients({}, this.mutatorOptions(options));

    /**
     * Create a tenant-owned service client with its first browser-generated
     * public assertion key. (`POST /api/CreateServiceClient`).
     */
    createServiceClient = (
        req: CreateServiceClientRequest,
        options?: CasRequestOptions,
    ): Promise<CreateServiceClientResponse> =>
        this.tenantServiceClient.createServiceClient(req, this.mutatorOptions(options));

    /**
     * Add an additional public assertion key to an existing service client.
     * (`POST /api/AddServiceClientKey`).
     */
    addServiceClientKey = (
        req: AddServiceClientKeyRequest,
        options?: CasRequestOptions,
    ): Promise<AddServiceClientKeyResponse> =>
        this.tenantServiceClient.addServiceClientKey(req, this.mutatorOptions(options));
}

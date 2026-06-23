import { ClientBase, type ClientBaseConfig } from '@onenexus/sdk-core';

import type {
    AddTenantUserRequest,
    CreateTenantRequest,
    CreateTenantResponse,
    CreateUserResponse,
    DescribeTenantRequest,
    DescribeTenantResponse,
    EmptyS3Request,
    ListS3AccountsResponse,
    ListS3OidcProvidersResponse,
    ListTenantsRequest,
    ListTenantsResponse,
    ListTenantUsersRequest,
    ListTenantUsersResponse,
    ProvisionS3DefaultAccountResponse,
    RegisterS3OidcProviderRequest,
    S3DefaultAccountResponse,
    S3OidcProviderDto,
    S3OidcProviderRequest,
    S3OperationResponse,
    UpdateS3OidcProviderThumbprintsRequest,
} from './generated/schemas/index.js';
import { getS3Administration } from './generated/s3-administration/s3-administration.js';
import { getTenant } from './generated/tenant/tenant.js';
import type { PlatformMutatorOptions } from './mutator.js';

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
export interface CasSupportClientConfig extends ClientBaseConfig {}

/**
 * Per-call options accepted by every {@link CasSupportClient} method.
 *
 * Today the only field is `signal` for cancellation; the type is named and
 * exported so future per-call overrides (custom headers, request-id, etc.)
 * can be added without changing every method signature.
 */
export type CasSupportRequestOptions = Omit<PlatformMutatorOptions, 'http'>;

/**
 * Typed client for the Central Auth Service Support API `/support-api/*` RPC
 * surface.
 *
 * This is the support-team operations surface — distinct from the regular CAS
 * client (`@onenexus/cas-client`, `/api/*`). It is generated from a separate
 * OpenAPI spec (`specs/cas-support/openapi.json`) and shares the same
 * transport, credential, and error primitives from `@onenexus/sdk-core`.
 *
 * Each method is a thin binding around an orval-generated function: the client
 * inherits {@link ClientBase}'s Ky transport, credentials, retry policy, and
 * client context, then passes the transport through to the mutator via the
 * second-argument options slot.
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
 * import { CasSupportClient } from '@onenexus/cas-support-client';
 * import { TokenGrantCredentials } from '@onenexus/sdk-core';
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
 *     name: 'tn_acme',
 *     displayName: 'Acme Inc',
 *     clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
 * });
 * ```
 */
export class CasSupportClient extends ClientBase {
    private readonly tenant: ReturnType<typeof getTenant>;
    private readonly s3: ReturnType<typeof getS3Administration>;

    constructor(config: CasSupportClientConfig) {
        super(config);
        this.tenant = getTenant();
        this.s3 = getS3Administration();
    }

    // -- Tenant management ---------------------------------------------------

    createTenant = (
        req: CreateTenantRequest,
        options?: CasSupportRequestOptions,
    ): Promise<CreateTenantResponse> => this.tenant.createTenant(req, this.mutatorOptions(options));

    describeTenant = (
        req: DescribeTenantRequest,
        options?: CasSupportRequestOptions,
    ): Promise<DescribeTenantResponse> =>
        this.tenant.describeTenant(req, this.mutatorOptions(options));

    listTenants = (
        req: ListTenantsRequest,
        options?: CasSupportRequestOptions,
    ): Promise<ListTenantsResponse> => this.tenant.listTenants(req, this.mutatorOptions(options));

    listTenantUsers = (
        req: ListTenantUsersRequest,
        options?: CasSupportRequestOptions,
    ): Promise<ListTenantUsersResponse> =>
        this.tenant.listTenantUsers(req, this.mutatorOptions(options));

    addTenantUser = (
        req: AddTenantUserRequest,
        options?: CasSupportRequestOptions,
    ): Promise<CreateUserResponse> => this.tenant.addTenantUser(req, this.mutatorOptions(options));

    // -- Ceph S3 administration ---------------------------------------------

    getS3DefaultAccount = (options?: CasSupportRequestOptions): Promise<S3DefaultAccountResponse> =>
        this.s3.getS3DefaultAccount(EMPTY_S3_REQUEST, this.mutatorOptions(options));

    provisionS3DefaultAccount = (
        options?: CasSupportRequestOptions,
    ): Promise<ProvisionS3DefaultAccountResponse> =>
        this.s3.provisionS3DefaultAccount(EMPTY_S3_REQUEST, this.mutatorOptions(options));

    listS3Accounts = (options?: CasSupportRequestOptions): Promise<ListS3AccountsResponse> =>
        this.s3.listS3Accounts(EMPTY_S3_REQUEST, this.mutatorOptions(options));

    listS3OidcProviders = (
        options?: CasSupportRequestOptions,
    ): Promise<ListS3OidcProvidersResponse> =>
        this.s3.listS3OidcProviders(EMPTY_S3_REQUEST, this.mutatorOptions(options));

    getS3OidcProvider = (
        req: S3OidcProviderRequest,
        options?: CasSupportRequestOptions,
    ): Promise<S3OidcProviderDto> => this.s3.getS3OidcProvider(req, this.mutatorOptions(options));

    registerS3OidcProvider = (
        req: RegisterS3OidcProviderRequest,
        options?: CasSupportRequestOptions,
    ): Promise<S3OidcProviderDto> =>
        this.s3.registerS3OidcProvider(req, this.mutatorOptions(options));

    updateS3OidcProviderThumbprints = (
        req: UpdateS3OidcProviderThumbprintsRequest,
        options?: CasSupportRequestOptions,
    ): Promise<S3OidcProviderDto> =>
        this.s3.updateS3OidcProviderThumbprints(req, this.mutatorOptions(options));

    deleteS3OidcProvider = (
        req: S3OidcProviderRequest,
        options?: CasSupportRequestOptions,
    ): Promise<S3OperationResponse> =>
        this.s3.deleteS3OidcProvider(req, this.mutatorOptions(options));
}

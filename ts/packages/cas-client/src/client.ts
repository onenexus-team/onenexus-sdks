import { ClientBase, type ClientBaseConfig } from '@onenexus-team/sdk-core';

import type {
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
    CreateAuthorizationRoleRequest,
    CreateAuthorizationRoleResponse,
    CreateServiceClientRequest,
    CreateServiceClientResponse,
    CreateUserRequest,
    CreateUserResponse,
    DeleteAuthorizationRoleRequest,
    DeleteAuthorizationRoleResponse,
    DeletePolicyRequest,
    DeletePolicyResponse,
    DetachPolicyFromRoleRequest,
    GetPolicyRequest,
    GetPolicyResponse,
    ListAuthorizationRolesRequest,
    ListAuthorizationRolesResponse,
    ListPoliciesRequest,
    ListPoliciesResponse,
    ListPolicyAttachmentsRequest,
    ListPolicyAttachmentsResponse,
    ListRoleAssignmentsRequest,
    ListRoleAssignmentsResponse,
    ListRolePoliciesRequest,
    ListS3RolesResponse,
    ListServiceClientsResponse,
    ListUsersRequest,
    ListUsersResponse,
    PublishPolicyRequest,
    PublishPolicyResponse,
    RemoveRoleAssignmentRequest,
    UpdatePolicyRequest,
    UpdatePolicyResponse,
} from './generated/schemas/index.js';
import { getAuthorizationAdministration } from './generated/authorization-administration/authorization-administration.js';
import { getAuthorizationPolicy } from './generated/authorization-policy/authorization-policy.js';
import { getAuthorizationRole } from './generated/authorization-role/authorization-role.js';
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
export type CasClientConfig = ClientBaseConfig;

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
    private readonly authorizationAdministration: ReturnType<
        typeof getAuthorizationAdministration
    >;
    private readonly authorizationPolicy: ReturnType<typeof getAuthorizationPolicy>;
    private readonly authorizationRole: ReturnType<typeof getAuthorizationRole>;
    private readonly tenantUser: ReturnType<typeof getTenantUser>;
    private readonly tenantS3: ReturnType<typeof getTenantS3>;
    private readonly tenantServiceClient: ReturnType<typeof getTenantServiceClient>;

    constructor(config: CasClientConfig) {
        super(config);
        this.authorizationAdministration = getAuthorizationAdministration();
        this.authorizationPolicy = getAuthorizationPolicy();
        this.authorizationRole = getAuthorizationRole();
        this.tenantUser = getTenantUser();
        this.tenantS3 = getTenantS3();
        this.tenantServiceClient = getTenantServiceClient();
    }

    // -- Tenant user management ----------------------------------------------

    /**
     * Admin invites a user into their own tenant and triggers the invite email.
     *
     * CAS derives the tenant from the caller's access token. The user stays pending until they redeem
     * the emailed invitation and set a password.
     *
     * @see POST /api/CreateUser
     */
    createUser = (
        req: CreateUserRequest,
        options?: CasRequestOptions,
    ): Promise<CreateUserResponse> => this.tenantUser.createUser(req, this.mutatorOptions(options));

    /**
     * Lists users in the authenticated caller's own tenant.
     *
     * CAS always lists the caller's tenant; do not send a tenant identifier. Results include root and
     * member users. Send one returned cursor at a time to move backward or forward through the list.
     *
     * @see POST /api/ListUsers
     */
    listUsers = (
        req: ListUsersRequest = {},
        options?: CasRequestOptions,
    ): Promise<ListUsersResponse> =>
        this.tenantUser.listUsers(req, this.mutatorOptions(options));

    /**
     * Redeems an invitation, sets a password, and activates the account.
     *
     * This endpoint does not require an access token. It accepts the invitation details delivered by
     * email, and an invitation can be used only once. On success, follow `loginUrl` to sign in.
     *
     * @see POST /api/AcceptInvitation
     */
    acceptInvitation = (
        req: AcceptInvitationRequest,
        options?: CasRequestOptions,
    ): Promise<AcceptInvitationResponse> =>
        this.tenantUser.acceptInvitation(req, this.mutatorOptions(options));

    // -- Tenant S3 -----------------------------------------------------------

    /**
     * List the S3 IAM roles provisioned in the caller's tenant account.
     *
     * CAS derives the tenant from the access token; this request cannot list another tenant's S3
     * roles. Each result includes the role's trust and inline permission policies for display in
     * tenant administration tools.
     *
     * @see POST /api/ListS3Roles
     */
    listS3Roles = (options?: CasRequestOptions): Promise<ListS3RolesResponse> =>
        this.tenantS3.listS3Roles({}, this.mutatorOptions(options));

    /**
     * Assume an S3 role in the caller's tenant account and return temporary credentials.
     *
     * CAS authorizes the requested role before issuing credentials. Use the returned access key,
     * secret, and session token for S3 requests until `expiration`; never persist or share the
     * temporary secret.
     *
     * @see POST /api/AssumeS3Role
     */
    assumeS3Role = (
        req: AssumeS3RoleRequest,
        options?: CasRequestOptions,
    ): Promise<AssumeS3RoleResponse> =>
        this.tenantS3.assumeS3Role(req, this.mutatorOptions(options));

    // -- Tenant service clients --------------------------------------------

    /**
     * List OAuth service clients owned by the caller's tenant.
     *
     * CAS derives the tenant from the access token. The response includes client identifiers and
     * registered public keys, never private keys.
     *
     * @see POST /api/ListServiceClients
     */
    listServiceClients = (options?: CasRequestOptions): Promise<ListServiceClientsResponse> =>
        this.tenantServiceClient.listServiceClients({}, this.mutatorOptions(options));

    /**
     * Create a tenant-owned service client with its first browser-generated public assertion key.
     *
     * Generate the key pair in your application or browser and submit only the public JWK. CAS returns
     * the `clientId` needed at the token endpoint; it never receives or stores the corresponding
     * private key.
     *
     * @see POST /api/CreateServiceClient
     */
    createServiceClient = (
        req: CreateServiceClientRequest,
        options?: CasRequestOptions,
    ): Promise<CreateServiceClientResponse> =>
        this.tenantServiceClient.createServiceClient(req, this.mutatorOptions(options));

    /**
     * Add an additional public assertion key to a service client.
     *
     * Use this to rotate a client key without interrupting the old key. CAS accepts at most three
     * public keys per service client; retain the private key outside CAS.
     *
     * @see POST /api/AddServiceClientKey
     */
    addServiceClientKey = (
        req: AddServiceClientKeyRequest,
        options?: CasRequestOptions,
    ): Promise<AddServiceClientKeyResponse> =>
        this.tenantServiceClient.addServiceClientKey(req, this.mutatorOptions(options));

    // -- Authorization roles -----------------------------------------------

    /**
     * Idempotently creates one tenant authorization role.
     *
     * Role names are case-sensitive ASCII letters and digits. The role is scoped to the caller's
     * tenant; creating an existing role with the same name succeeds and returns `created: false`.
     *
     * @see POST /api/CreateRole
     */
    createRole = (
        req: CreateAuthorizationRoleRequest,
        options?: CasRequestOptions,
    ): Promise<CreateAuthorizationRoleResponse> =>
        this.authorizationRole.createRole(req, this.mutatorOptions(options));

    /**
     * Lists authorization roles in the caller's tenant.
     *
     * Results are ordered by role name. The returned `roleUri` is the stable identifier to use when
     * assigning roles or attaching policies.
     *
     * @see POST /api/ListRoles
     */
    listRoles = (
        req: ListAuthorizationRolesRequest = {},
        options?: CasRequestOptions,
    ): Promise<ListAuthorizationRolesResponse> =>
        this.authorizationRole.listRoles(req, this.mutatorOptions(options));

    /**
     * Deletes one unreferenced tenant authorization role. Direct grants, workload bindings, and policy
     * attachments must be removed explicitly before deletion; CAS never cascades those relationships.
     *
     * Remove every direct user, service-client, workload, and policy relationship first. CAS does not
     * cascade deletion, which prevents a role from disappearing unexpectedly from an access
     * configuration.
     *
     * @see POST /api/DeleteRole
     */
    deleteRole = (
        req: DeleteAuthorizationRoleRequest,
        options?: CasRequestOptions,
    ): Promise<DeleteAuthorizationRoleResponse> =>
        this.authorizationRole.deleteRole(req, this.mutatorOptions(options));

    // -- Authorization relationships ---------------------------------------

    /**
     * Idempotently assigns one role to a user or service client.
     *
     * The assignee and role must belong to the caller's tenant. Repeating the same request does not
     * create a second assignment; inspect `created` to tell whether CAS created it on this call.
     *
     * @see POST /api/AssignRole
     */
    assignRole = (
        req: AssignRoleRequest,
        options?: CasRequestOptions,
    ): Promise<AssignRoleResponse> =>
        this.authorizationAdministration.assignRole(req, this.mutatorOptions(options));

    /**
     * Removes one direct role assignment using its current state token.
     *
     * First obtain the assignment with `ListRoleAssignments`, then send its `stateToken`. CAS rejects
     * a stale token so an administrator cannot remove a relationship that changed after it was
     * displayed.
     *
     * @see POST /api/RemoveRoleAssignment
     */
    removeRoleAssignment = (
        req: RemoveRoleAssignmentRequest,
        options?: CasRequestOptions,
    ): Promise<AuthorizationRelationshipRemovedResponse> =>
        this.authorizationAdministration.removeRoleAssignment(req, this.mutatorOptions(options));

    /**
     * Lists direct assignments by exactly one role or assignee filter.
     *
     * Provide exactly one of `roleUri` or `assignee`. Use the returned `before` or `after` value
     * unchanged to navigate pages; do not send both cursors in one request.
     *
     * @see POST /api/ListRoleAssignments
     */
    listRoleAssignments = (
        req: ListRoleAssignmentsRequest = {},
        options?: CasRequestOptions,
    ): Promise<ListRoleAssignmentsResponse> =>
        this.authorizationAdministration.listRoleAssignments(req, this.mutatorOptions(options));

    /**
     * Compiles and idempotently attaches one tenant- or platform-managed policy to a role.
     *
     * A direct attachment makes the policy available whenever the role is evaluated. Repeating the
     * same request preserves the existing relationship and returns `created: false`.
     *
     * @see POST /api/AttachPolicyToRole
     */
    attachPolicyToRole = (
        req: AttachPolicyToRoleRequest,
        options?: CasRequestOptions,
    ): Promise<AttachPolicyToRoleResponse> =>
        this.authorizationAdministration.attachPolicyToRole(req, this.mutatorOptions(options));

    /**
     * Detaches one policy from one role using the relationship state token.
     *
     * Get the attachment first with `ListPolicyAttachments` or `ListRolePolicies`, then provide its
     * `stateToken`. This protects against deleting a relationship that changed concurrently.
     *
     * @see POST /api/DetachPolicyFromRole
     */
    detachPolicyFromRole = (
        req: DetachPolicyFromRoleRequest,
        options?: CasRequestOptions,
    ): Promise<AuthorizationRelationshipRemovedResponse> =>
        this.authorizationAdministration.detachPolicyFromRole(req, this.mutatorOptions(options));

    /**
     * Lists roles to which one policy is directly attached.
     *
     * The response contains the direct policy-to-role relationships, not the users or service clients
     * that inherit access through those roles. Use the returned cursors for paging.
     *
     * @see POST /api/ListPolicyAttachments
     */
    listPolicyAttachments = (
        req: ListPolicyAttachmentsRequest,
        options?: CasRequestOptions,
    ): Promise<ListPolicyAttachmentsResponse> =>
        this.authorizationAdministration.listPolicyAttachments(req, this.mutatorOptions(options));

    /**
     * Lists tenant- and platform-managed policies directly attached to one role.
     *
     * This returns only direct attachments. A policy inherited by another mechanism is not included.
     * Use the returned cursors for paging.
     *
     * @see POST /api/ListRolePolicies
     */
    listRolePolicies = (
        req: ListRolePoliciesRequest,
        options?: CasRequestOptions,
    ): Promise<ListPolicyAttachmentsResponse> =>
        this.authorizationAdministration.listRolePolicies(req, this.mutatorOptions(options));

    // -- Authorization policies --------------------------------------------

    /**
     * Validates and publishes new tenant-managed policy content.
     *
     * Creates a policy in the caller's tenant after validating its document. A rejected response
     * includes safe diagnostics and creates no usable policy. Reuse the same `requestId` when retrying
     * a timed-out call.
     *
     * @see POST /api/PublishPolicy
     */
    publishPolicy = (
        req: PublishPolicyRequest,
        options?: CasRequestOptions,
    ): Promise<PublishPolicyResponse> =>
        this.authorizationPolicy.publishPolicy(req, this.mutatorOptions(options));

    /**
     * Lists one page of policies visible to the caller's tenant.
     *
     * Returns the tenant's own policies and platform-managed policies that are available to that
     * tenant. Send at most one returned cursor in the next request to move backward or forward through
     * the result set.
     *
     * @see POST /api/ListPolicies
     */
    listPolicies = (
        req: ListPoliciesRequest = {},
        options?: CasRequestOptions,
    ): Promise<ListPoliciesResponse> =>
        this.authorizationPolicy.listPolicies(req, this.mutatorOptions(options));

    /**
     * Gets one policy's content without its role attachments.
     *
     * Use this before editing a policy to obtain its current `contentStateToken`. Attachments are
     * managed separately with the policy-to-role APIs.
     *
     * @see POST /api/GetPolicy
     */
    getPolicy = (
        req: GetPolicyRequest,
        options?: CasRequestOptions,
    ): Promise<GetPolicyResponse> =>
        this.authorizationPolicy.getPolicy(req, this.mutatorOptions(options));

    /**
     * Updates only the content of an existing tenant-managed policy.
     *
     * Send the `contentStateToken` returned by the latest read or successful write. CAS rejects stale
     * updates rather than overwriting a concurrent change. Platform-managed policies cannot be edited
     * here.
     *
     * @see POST /api/UpdatePolicy
     */
    updatePolicy = (
        req: UpdatePolicyRequest,
        options?: CasRequestOptions,
    ): Promise<UpdatePolicyResponse> =>
        this.authorizationPolicy.updatePolicy(req, this.mutatorOptions(options));

    /**
     * Deletes one unattached tenant-managed policy.
     *
     * Remove every direct role attachment before deleting a policy. Send its current
     * `contentStateToken` so CAS can reject a delete based on an out-of-date view. Platform-managed
     * policies cannot be deleted here.
     *
     * @see POST /api/DeletePolicy
     */
    deletePolicy = (
        req: DeletePolicyRequest,
        options?: CasRequestOptions,
    ): Promise<DeletePolicyResponse> =>
        this.authorizationPolicy.deletePolicy(req, this.mutatorOptions(options));
}

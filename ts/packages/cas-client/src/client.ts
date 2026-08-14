import {
    ClientBase,
    type ClientBaseConfig,
    type ClientRequestOptions,
} from '@onenexus-team/sdk-core';

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
    DisableServiceClientRequest,
    DisableServiceClientResponse,
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
    RemoveServiceClientKeyRequest,
    RemoveServiceClientKeyResponse,
    ResendUserInvitationRequest,
    UpdateAuthorizationRoleDescriptionRequest,
    UpdateAuthorizationRoleDescriptionResponse,
    UpdatePolicyRequest,
    UpdatePolicyResponse,
} from './generated/models/index.js';
import { createCasApiClient, type CasApiClient } from './generated/casApiClient.js';

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
export type CasRequestOptions = ClientRequestOptions;

type NumericLimitRequest<T extends { limit?: unknown }> = Omit<T, 'limit'> & {
    readonly limit?: T['limit'] | number | string;
};

/**
 * Typed client for the Central Auth Service Customer API `/api/*` RPC surface.
 *
 * This is the customer-facing user surface (`CreateUser`, `AcceptInvitation`).
 * Tenant-management and support operations live in a separate spec and are
 * served by `@onenexus-team/cas-support-client` (`/support-api/*`).
 *
 * Each method is a thin binding around a Kiota-generated request builder. The
 * client inherits {@link ClientBase}'s request adapter, credentials, native
 * retry policy, timeout behavior, and skew-aware client context.
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
 *     requestId: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
 * });
 * ```
 */
export class CasClient extends ClientBase {
    private readonly kiota: CasApiClient;

    constructor(config: CasClientConfig) {
        super(config);
        this.kiota = createCasApiClient(this.requestAdapter);
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
    ): Promise<CreateUserResponse> =>
        this.expectResponse(
            this.kiota.api.createUser.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Lists users in the authenticated caller's own tenant.
     *
     * CAS always lists the caller's tenant; do not send a tenant identifier. Results include root and
     * member users. Send one returned cursor at a time to move backward or forward through the list.
     *
     * @see POST /api/ListUsers
     */
    listUsers = (
        req: NumericLimitRequest<ListUsersRequest> = {},
        options?: CasRequestOptions,
    ): Promise<ListUsersResponse> =>
        this.expectResponse(
            this.kiota.api.listUsers.post(
                req as ListUsersRequest,
                this.requestConfiguration(req, options),
            ),
        );

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
        this.expectResponse(
            this.kiota.api.acceptInvitation.post(req, this.requestConfiguration(req, options)),
        );

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
    listS3Roles = (options?: CasRequestOptions): Promise<ListS3RolesResponse> => {
        const body = {};
        return this.expectResponse(
            this.kiota.api.listS3Roles.post(body, this.requestConfiguration(body, options)),
        );
    };

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
        this.expectResponse(
            this.kiota.api.assumeS3Role.post(req, this.requestConfiguration(req, options)),
        );

    // -- Tenant service clients --------------------------------------------

    /**
     * List OAuth service clients owned by the caller's tenant.
     *
     * CAS derives the tenant from the access token. The response includes client identifiers and
     * registered public keys, never private keys.
     *
     * @see POST /api/ListServiceClients
     */
    listServiceClients = (options?: CasRequestOptions): Promise<ListServiceClientsResponse> => {
        const body = {};
        return this.expectResponse(
            this.kiota.api.listServiceClients.post(body, this.requestConfiguration(body, options)),
        );
    };

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
        this.expectResponse(
            this.kiota.api.createServiceClient.post(req, this.requestConfiguration(req, options)),
        );

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
        this.expectResponse(
            this.kiota.api.addServiceClientKey.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Revokes one public assertion key from a service client.
     *
     * The final key cannot be removed. Disable the service client when its only key is compromised.
     *
     * @see POST /api/RemoveServiceClientKey
     */
    removeServiceClientKey = (
        req: RemoveServiceClientKeyRequest,
        options?: CasRequestOptions,
    ): Promise<RemoveServiceClientKeyResponse> =>
        this.expectResponse(
            this.kiota.api.removeServiceClientKey.post(
                req,
                this.requestConfiguration(req, options),
            ),
        );

    /**
     * Disables a service client so it cannot obtain new access tokens.
     *
     * The operation is idempotent. Already-issued short-lived access tokens retain their normal
     * expiry; disabling prevents subsequent token issuance.
     *
     * @see POST /api/DisableServiceClient
     */
    disableServiceClient = (
        req: DisableServiceClientRequest,
        options?: CasRequestOptions,
    ): Promise<DisableServiceClientResponse> =>
        this.expectResponse(
            this.kiota.api.disableServiceClient.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Re-sends an invitation to a pending member in the caller's tenant.
     *
     * CAS derives the tenant from the authenticated caller. Tenant roots and users in other tenants
     * cannot be targeted through this operation.
     *
     * @see POST /api/ResendUserInvitation
     */
    resendUserInvitation = (
        req: ResendUserInvitationRequest,
        options?: CasRequestOptions,
    ): Promise<void> =>
        this.expectNoResponse(
            this.kiota.api.resendUserInvitation.post(req, this.requestConfiguration(req, options)),
        );

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
        this.expectResponse(
            this.kiota.api.createRole.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Updates the optional human-readable description of one tenant role.
     *
     * Send `null` or omit `description` to clear it; role names and URIs remain immutable.
     *
     * @see POST /api/UpdateRoleDescription
     */
    updateRoleDescription = (
        req: UpdateAuthorizationRoleDescriptionRequest,
        options?: CasRequestOptions,
    ): Promise<UpdateAuthorizationRoleDescriptionResponse> =>
        this.expectResponse(
            this.kiota.api.updateRoleDescription.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Lists authorization roles in the caller's tenant.
     *
     * Results are ordered by role name. The returned `roleUri` is the stable identifier to use when
     * assigning roles or attaching policies.
     *
     * @see POST /api/ListRoles
     */
    listRoles = (
        req: NumericLimitRequest<ListAuthorizationRolesRequest> = {},
        options?: CasRequestOptions,
    ): Promise<ListAuthorizationRolesResponse> =>
        this.expectResponse(
            this.kiota.api.listRoles.post(
                req as ListAuthorizationRolesRequest,
                this.requestConfiguration(req, options),
            ),
        );

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
        this.expectResponse(
            this.kiota.api.deleteRole.post(req, this.requestConfiguration(req, options)),
        );

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
        this.expectResponse(
            this.kiota.api.assignRole.post(req, this.requestConfiguration(req, options)),
        );

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
        this.expectResponse(
            this.kiota.api.removeRoleAssignment.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Lists direct assignments by exactly one role or assignee filter.
     *
     * Provide exactly one of `roleUri` or `assignee`. Use the returned `before` or `after` value
     * unchanged to navigate pages; do not send both cursors in one request.
     *
     * @see POST /api/ListRoleAssignments
     */
    listRoleAssignments = (
        req: NumericLimitRequest<ListRoleAssignmentsRequest> = {},
        options?: CasRequestOptions,
    ): Promise<ListRoleAssignmentsResponse> =>
        this.expectResponse(
            this.kiota.api.listRoleAssignments.post(
                req as ListRoleAssignmentsRequest,
                this.requestConfiguration(req, options),
            ),
        );

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
        this.expectResponse(
            this.kiota.api.attachPolicyToRole.post(req, this.requestConfiguration(req, options)),
        );

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
        this.expectResponse(
            this.kiota.api.detachPolicyFromRole.post(req, this.requestConfiguration(req, options)),
        );

    /**
     * Lists roles to which one policy is directly attached.
     *
     * The response contains the direct policy-to-role relationships, not the users or service clients
     * that inherit access through those roles. Use the returned cursors for paging.
     *
     * @see POST /api/ListPolicyAttachments
     */
    listPolicyAttachments = (
        req: NumericLimitRequest<ListPolicyAttachmentsRequest>,
        options?: CasRequestOptions,
    ): Promise<ListPolicyAttachmentsResponse> =>
        this.expectResponse(
            this.kiota.api.listPolicyAttachments.post(
                req as ListPolicyAttachmentsRequest,
                this.requestConfiguration(req, options),
            ),
        );

    /**
     * Lists tenant- and platform-managed policies directly attached to one role.
     *
     * This returns only direct attachments. A policy inherited by another mechanism is not included.
     * Use the returned cursors for paging.
     *
     * @see POST /api/ListRolePolicies
     */
    listRolePolicies = (
        req: NumericLimitRequest<ListRolePoliciesRequest>,
        options?: CasRequestOptions,
    ): Promise<ListPolicyAttachmentsResponse> =>
        this.expectResponse(
            this.kiota.api.listRolePolicies.post(
                req as ListRolePoliciesRequest,
                this.requestConfiguration(req, options),
            ),
        );

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
        this.expectResponse(
            this.kiota.api.publishPolicy.post(req, this.requestConfiguration(req, options)),
        );

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
        req: NumericLimitRequest<ListPoliciesRequest> = {},
        options?: CasRequestOptions,
    ): Promise<ListPoliciesResponse> =>
        this.expectResponse(
            this.kiota.api.listPolicies.post(
                req as ListPoliciesRequest,
                this.requestConfiguration(req, options),
            ),
        );

    /**
     * Gets one policy's content without its role attachments.
     *
     * Use this before editing a policy to obtain its current `contentStateToken`. Attachments are
     * managed separately with the policy-to-role APIs.
     *
     * @see POST /api/GetPolicy
     */
    getPolicy = (req: GetPolicyRequest, options?: CasRequestOptions): Promise<GetPolicyResponse> =>
        this.expectResponse(
            this.kiota.api.getPolicy.post(req, this.requestConfiguration(req, options)),
        );

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
        this.expectResponse(
            this.kiota.api.updatePolicy.post(req, this.requestConfiguration(req, options)),
        );

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
        this.expectResponse(
            this.kiota.api.deletePolicy.post(req, this.requestConfiguration(req, options)),
        );
}

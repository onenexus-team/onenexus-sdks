import { readFile } from 'node:fs/promises';

import type { TokenEndpointResponse, ServerMetadata } from 'openid-client';

import type { AccessToken, ClientContext, Credentials } from '../credentials/credentials.js';
import { AuthenticationError } from '../credentials/credentials.js';
import {
    isNearExpiry,
    isUnauthorizedError,
    toAccessToken,
} from '../credentials/internal/oidc-bridge.js';

/**
 * The custom OAuth grant type CAS recognises for the workload-identity file
 * exchange. The workload presents the file token as `subject_token` with
 * {@link WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE}, and CAS mints a CAS access token in
 * return.
 *
 * It is a custom grant (not RFC 8693 token-exchange) because the presented
 * token is an *external* identity token, not a CAS-issued `subject_token`.
 */
export const WORKLOAD_IDENTITY_GRANT_TYPE =
    'urn:onenexus:params:oauth:grant-type:workload-identity';

/** Custom `subject_token_type` value for workload-identity file tokens. */
export const WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE = 'urn:ietf:params:oauth:token-type:jwt';

/**
 * Neutral default mount path for the workload-identity token. Platform deployments
 * project their runtime identity token to this path; on Kubernetes that is a
 * projected ServiceAccount token volume mounted here.
 */
export const DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH = '/var/run/secrets/onenexus/token';

/**
 * Configuration for {@link WorkloadIdentityFileCredentials}.
 *
 * Runtime-agnostic by design: the credential knows only about *a file that
 * contains a token*. A workload running inside the OneNexus platform points
 * `tokenPath` at whatever file its runtime mounts (on Kubernetes that is the
 * projected ServiceAccount token), and CAS exchanges that token for a CAS
 * access token.
 */
export interface WorkloadIdentityFileCredentialsConfig {
    readonly issuer: string;
    /**
     * Path to the runtime-mounted identity token. Defaults to
     * {@link DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH}. Override in tests or for
     * non-standard projections.
     */
    readonly tokenPath?: string;
    /**
     * Optional OAuth `client_id` compatibility override. By default this
     * credential sends no `client_id`; the workload identity is the file token.
     */
    readonly clientId?: string;
    readonly audience?: string;
    readonly scopes?: readonly string[];
    /** Pre-resolved server metadata. When supplied, skips OIDC discovery. */
    readonly serverMetadata?: ServerMetadata;
}

/**
 * Exchange a file-mounted identity token for a CAS access token.
 *
 * On each refresh, reads the token from `tokenPath` on disk and presents it to
 * CAS under the {@link WORKLOAD_IDENTITY_GRANT_TYPE} grant. Caches the resulting CAS
 * access token until shortly before expiry; concurrent `resolve()` calls during
 * a refresh share one in-flight request (single-flight).
 *
 * **Node-only.** Lives under the `@onenexus/sdk-core/node` subpath because the
 * token mount is a Node filesystem read. Browser bundles cannot include this;
 * importing this subpath in a browser build errors on `node:fs/promises`.
 *
 * Refresh re-reads the token from disk on every call — the runtime rotates the
 * projection in place, so caching the file token in memory would risk using a
 * stale one. Caching the CAS access token (the exchange result) is what
 * amortises the cost across many `resolve()` calls.
 */
export class WorkloadIdentityFileCredentials implements Credentials {
    private readonly config: WorkloadIdentityFileCredentialsConfig;
    private metadataPromise: Promise<ServerMetadata> | undefined;
    private cached: AccessToken | undefined;
    private refreshInFlight: Promise<AccessToken> | undefined;

    constructor(config: WorkloadIdentityFileCredentialsConfig) {
        this.config = config;
    }

    async resolve(context: ClientContext, signal?: AbortSignal): Promise<AccessToken> {
        if (this.cached && !isNearExpiry(this.cached, context.clock, context.refreshLeewayMs)) {
            return this.cached;
        }
        if (this.refreshInFlight) {
            return this.refreshInFlight;
        }

        const refresh = this.refresh(context, signal).then(
            (token) => {
                this.cached = token;
                return token;
            },
            (error: unknown) => {
                this.refreshInFlight = undefined;
                throw error;
            },
        );
        this.refreshInFlight = refresh;
        try {
            return await refresh;
        } finally {
            this.refreshInFlight = undefined;
        }
    }

    private getMetadata(): Promise<ServerMetadata> {
        this.metadataPromise ??= this.resolveMetadata();
        return this.metadataPromise;
    }

    private async resolveMetadata(): Promise<ServerMetadata> {
        if (this.config.serverMetadata) {
            return this.config.serverMetadata;
        }
        const response = await fetch(
            `${this.config.issuer.replace(/\/$/, '')}/.well-known/openid-configuration`,
            {
                headers: { Accept: 'application/json' },
            },
        );
        if (!response.ok) {
            throw Object.assign(new Error('Workload identity OIDC discovery failed.'), {
                response: { status: response.status },
            });
        }
        return (await response.json()) as ServerMetadata;
    }

    private async refresh(context: ClientContext, _signal?: AbortSignal): Promise<AccessToken> {
        const tokenPath = this.config.tokenPath ?? DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH;
        // Read on every refresh — the runtime rotates the projection in place.
        const identityToken = (await readFile(tokenPath, 'utf-8')).trim();

        const metadata = await this.getMetadata();
        const parameters: Record<string, string> = {
            grant_type: WORKLOAD_IDENTITY_GRANT_TYPE,
            subject_token: identityToken,
            subject_token_type: WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE,
        };
        if (this.config.clientId !== undefined) parameters['client_id'] = this.config.clientId;
        if (this.config.audience !== undefined) parameters['audience'] = this.config.audience;
        if (this.config.scopes !== undefined && this.config.scopes.length > 0) {
            parameters['scope'] = this.config.scopes.join(' ');
        }

        try {
            const tokenEndpoint = metadata.token_endpoint;
            if (tokenEndpoint === undefined) {
                throw new Error('Workload identity OIDC metadata is missing token_endpoint.');
            }

            const response = await fetch(tokenEndpoint, {
                method: 'POST',
                body: new URLSearchParams(parameters),
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            });
            if (!response.ok) {
                throw Object.assign(new Error('Workload identity token request failed.'), {
                    response: { status: response.status },
                });
            }
            const payload = (await response.json()) as TokenEndpointResponse;
            return toAccessToken(payload, context.clock);
        } catch (error) {
            if (isUnauthorizedError(error)) {
                throw new AuthenticationError(
                    'WorkloadIdentityFileCredentials: the workload identity token was rejected.',
                    { cause: error },
                );
            }
            throw error;
        }
    }
}

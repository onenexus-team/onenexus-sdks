import { Configuration, discovery, None, refreshTokenGrant, type ServerMetadata } from 'openid-client';

import type { AccessToken, ClientContext, Credentials } from './credentials.js';
import { AuthenticationError, StaleCredentialsError } from './credentials.js';
import { isNearExpiry, isUnauthorizedError, toTokenGrant } from './internal/oidc-bridge.js';

/**
 * Configuration for {@link TokenGrantCredentials}.
 *
 * `token` is the access token used for API calls. Refresh token, ID token, and
 * scopes are grant metadata owned by this credential, not by the access-token
 * value. If refresh-token grant settings are supplied, this credential refreshes
 * transparently when the access token is near expiry.
 */
export interface TokenGrantCredentialsConfig {
    readonly token: AccessToken;
    readonly refreshToken?: string;
    readonly idToken?: string;
    readonly scopes?: readonly string[];
    readonly issuer?: string;
    readonly clientId?: string;
    readonly serverMetadata?: ServerMetadata;
    /** Overrides the client context's refresh leeway for this credential. */
    readonly refreshLeewayMs?: number;
}

/**
 * Credentials backed by a token grant.
 *
 * Useful when:
 * - The caller obtained the grant externally and wants to feed it into a
 *   service client unchanged.
 * - Acting as the leaf of a future credential composition that wraps a user's
 *   inbound access token.
 *
 * When no refresh token is configured, an expired access token raises
 * {@link StaleCredentialsError}. When refresh is configured, refresh-token
 * grant failures caused by authentication rejection raise
 * {@link AuthenticationError}.
 */
export class TokenGrantCredentials implements Credentials {
    private cached: AccessToken;
    private refreshToken: string | undefined;
    private currentIdToken: string | undefined;
    private currentScopes: readonly string[];
    private readonly config: TokenGrantCredentialsConfig;
    private readonly refreshLeewayMs: number | undefined;
    private configurationPromise: Promise<Configuration> | undefined;
    private refreshInFlight: Promise<AccessToken> | undefined;

    constructor(config: TokenGrantCredentialsConfig) {
        this.config = config;
        this.cached = config.token;
        this.refreshToken = config.refreshToken;
        this.currentIdToken = config.idToken;
        this.currentScopes = config.scopes ?? [];
        this.refreshLeewayMs = config.refreshLeewayMs;
    }

    get idToken(): string | undefined {
        return this.currentIdToken;
    }

    get scopes(): readonly string[] {
        return this.currentScopes;
    }

    async resolve(context: ClientContext, signal?: AbortSignal): Promise<AccessToken> {
        if (!isNearExpiry(this.cached, context.clock, this.effectiveRefreshLeewayMs(context))) {
            return this.cached;
        }

        if (this.refreshInFlight) {
            return this.refreshInFlight;
        }
        
        if (!this.canRefresh()) {
            throw new StaleCredentialsError(
                'TokenGrantCredentials: access token is stale and no refresh-token grant is configured.',
            );
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

    snapshot(): TokenGrantCredentialsConfig {
        return {
            token: this.cached,
            ...(this.refreshToken !== undefined && { refreshToken: this.refreshToken }),
            ...(this.currentIdToken !== undefined && { idToken: this.currentIdToken }),
            scopes: this.currentScopes,
            ...(this.config.issuer !== undefined && { issuer: this.config.issuer }),
            ...(this.config.clientId !== undefined && { clientId: this.config.clientId }),
            ...(this.config.serverMetadata !== undefined && { serverMetadata: this.config.serverMetadata }),
            ...(this.refreshLeewayMs !== undefined && { refreshLeewayMs: this.refreshLeewayMs }),
        };
    }

    private effectiveRefreshLeewayMs(context: ClientContext): number {
        return this.refreshLeewayMs ?? context.refreshLeewayMs;
    }

    private canRefresh(): boolean {
        return (
            this.refreshToken !== undefined &&
            this.config.clientId !== undefined &&
            (this.config.issuer !== undefined || this.config.serverMetadata !== undefined)
        );
    }

    private getConfiguration(): Promise<Configuration> {
        if (!this.canRefresh()) {
            throw new StaleCredentialsError(
                'TokenGrantCredentials: refresh-token grant settings are incomplete.',
            );
        }

        this.configurationPromise ??= this.buildConfiguration();
        return this.configurationPromise;
    }

    private async buildConfiguration(): Promise<Configuration> {
        if (this.config.clientId === undefined) {
            throw new StaleCredentialsError('TokenGrantCredentials: missing clientId for refresh.');
        }

        const clientAuth = None();
        if (this.config.serverMetadata) {
            return new Configuration(
                this.config.serverMetadata,
                this.config.clientId,
                undefined,
                clientAuth,
            );
        }
        if (this.config.issuer === undefined) {
            throw new StaleCredentialsError('TokenGrantCredentials: missing issuer for refresh.');
        }
        return discovery(new URL(this.config.issuer), this.config.clientId, undefined, clientAuth);
    }

    private async refresh(context: ClientContext, _signal?: AbortSignal): Promise<AccessToken> {
        if (this.refreshToken === undefined) {
            throw new StaleCredentialsError('TokenGrantCredentials: missing refresh token.');
        }

        try {
            const configuration = await this.getConfiguration();
            const response = await refreshTokenGrant(configuration, this.refreshToken);
            const grant = toTokenGrant(response, context.clock);

            if (grant.refreshToken !== undefined) {
                this.refreshToken = grant.refreshToken;
            }
            if (grant.idToken !== undefined) {
                this.currentIdToken = grant.idToken;
            }
            this.currentScopes = grant.scopes;

            return grant.token;
        } catch (error) {
            if (isUnauthorizedError(error)) {
                throw new AuthenticationError('TokenGrantCredentials: refresh token was rejected.', {
                    cause: error,
                });
            }
            throw error;
        }
    }
}

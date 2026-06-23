import {
    clientCredentialsGrant,
    Configuration,
    discovery,
    modifyAssertion,
    PrivateKeyJwt,
    type ServerMetadata,
} from 'openid-client';

import type { AccessToken, ClientContext, Credentials } from './credentials.js';
import { AuthenticationError } from './credentials.js';
import { isNearExpiry, isUnauthorizedError, toAccessToken } from './internal/oidc-bridge.js';

const CLIENT_ASSERTION_JWT_TYPE = 'client-authentication+jwt';

/**
 * Configuration for the Client Credentials grant with `private_key_jwt` client
 * authentication.
 *
 * The customer's backend signs short-lived client-assertion JWTs with the
 * private key registered at CAS; CAS validates them against the matching
 * public key.
 */
export interface PrivateKeyJwtCredentialsConfig {
    readonly issuer: string;
    readonly clientId: string;
    readonly audience?: string;
    readonly scopes?: readonly string[];
    /**
     * The private key used to sign client assertions. Web Crypto `CryptoKey`
     * is the canonical type — works in Node 20+ and browsers.
     */
    readonly signingKey: CryptoKey;
    /** Key identifier, surfaced as the JWT `kid` header. */
    readonly signingKeyId: string;
    /** JWS algorithm; defaults to `RS256`. */
    readonly signingAlgorithm?: 'RS256' | 'PS256' | 'ES256';
    /**
     * Pre-resolved server metadata. When supplied, skips OIDC discovery —
     * useful for environments where the auth server can't host
     * `/.well-known/openid-configuration` or for offline tests against a
     * stable known endpoint.
     */
    readonly serverMetadata?: ServerMetadata;
}

/**
 * Scenario 3.1b — Customer backend with a registered keypair.
 *
 * Signs short-lived client assertions for the Client Credentials grant and
 * caches the resulting access token until shortly before its expiry.
 * Concurrent `resolve()` calls during a refresh share one in-flight request
 * (single-flight); after refresh, the cached token serves subsequent calls
 * until it nears expiry.
 */
export class PrivateKeyJwtCredentials implements Credentials {
    private readonly config: PrivateKeyJwtCredentialsConfig;
    private configurationPromise: Promise<Configuration> | undefined;
    private cached: AccessToken | undefined;
    private refreshInFlight: Promise<AccessToken> | undefined;

    constructor(config: PrivateKeyJwtCredentialsConfig) {
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
                // Don't poison the cache with a rejected promise.
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

    /** Lazily build (or reuse) the openid-client `Configuration`. */
    private getConfiguration(): Promise<Configuration> {
        this.configurationPromise ??= this.buildConfiguration();
        return this.configurationPromise;
    }

    private async buildConfiguration(): Promise<Configuration> {
        const clientAuth = PrivateKeyJwt(
            {
                key: this.config.signingKey,
                kid: this.config.signingKeyId,
            },
            {
                [modifyAssertion]: (header) => {
                    header['typ'] = CLIENT_ASSERTION_JWT_TYPE;
                },
            },
        );

        if (this.config.serverMetadata) {
            const configuration = new Configuration(
                this.config.serverMetadata,
                this.config.clientId,
                undefined,
                clientAuth,
            );
            return configuration;
        }
        return discovery(new URL(this.config.issuer), this.config.clientId, undefined, clientAuth);
    }

    private async refresh(context: ClientContext, _signal?: AbortSignal): Promise<AccessToken> {
        const configuration = await this.getConfiguration();
        const parameters: Record<string, string> = {};
        if (this.config.audience !== undefined) parameters['audience'] = this.config.audience;
        if (this.config.scopes !== undefined && this.config.scopes.length > 0) {
            parameters['scope'] = this.config.scopes.join(' ');
        }
        try {
            const response = await clientCredentialsGrant(configuration, parameters);
            return toAccessToken(response, context.clock);
        } catch (error) {
            if (isUnauthorizedError(error)) {
                throw new AuthenticationError(
                    'PrivateKeyJwtCredentials: client assertion was rejected.',
                    { cause: error },
                );
            }
            throw error;
        }
    }
}

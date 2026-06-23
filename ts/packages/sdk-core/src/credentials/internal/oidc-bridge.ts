/**
 * Internal helpers shared by the active credential implementations
 * (`TokenGrantCredentials`, `PrivateKeyJwtCredentials`,
 * `WorkloadIdentityFileCredentials`).
 *
 * Not part of the public API.
 */

import type { TokenEndpointResponse } from 'openid-client';

import type { AccessToken, Clock } from '../credentials.js';

/**
 * Token-endpoint response converted into the SDK's domain shape.
 *
 * `token` is the value used for API access. The other fields are grant
 * metadata consumed by credential implementations such as TokenGrantCredentials.
 */
export interface OidcTokenGrant {
    readonly token: AccessToken;
    readonly refreshToken?: string;
    readonly idToken?: string;
    readonly scopes: readonly string[];
}

/**
 * Convert openid-client's `TokenEndpointResponse` (relative `expires_in`,
 * space-separated `scope` string, snake_case fields) into the platform's token
 * grant shape. The access token itself stays narrow; refresh token, ID token,
 * and scopes remain grant metadata for credential implementations.
 *
 * The fallback expiry (1 hour) applies when the server omits `expires_in` —
 * matches the OAuth 2.0 default per RFC 6749 §5.1.
 */
export function toTokenGrant(response: TokenEndpointResponse, clock: Clock): OidcTokenGrant {
    const now = clock.serverNow();
    const expiresInMs = response.expires_in !== undefined ? response.expires_in * 1000 : 3_600_000;
    const expiresAt = new Date(now + expiresInMs);

    return {
        token: {
            accessToken: response.access_token,
            tokenType: 'Bearer',
            expiresAt,
        },
        scopes: response.scope ? response.scope.split(' ') : [],
        // Conditional spreads — `exactOptionalPropertyTypes` rejects `: undefined`.
        ...(response.refresh_token !== undefined && { refreshToken: response.refresh_token }),
        ...(response.id_token !== undefined && { idToken: response.id_token }),
    };
}

/** Convert a token-endpoint response to just the API access token. */
export function toAccessToken(response: TokenEndpointResponse, clock: Clock): AccessToken {
    return toTokenGrant(response, clock).token;
}

/**
 * Whether `token` should be considered expired for refresh purposes. Uses a
 * 30-second leeway so a refresh kicks off before the token actually expires —
 * avoiding the race where the token expires mid-flight between resolve() and
 * the downstream request.
 */
export function isNearExpiry(token: AccessToken, clock: Clock, leewayMs = 30_000): boolean {
    return token.expiresAt.getTime() - clock.serverNow() <= leewayMs;
}

/** Whether an error shape represents a 401 authentication rejection. */
export function isUnauthorizedError(error: unknown): boolean {
    if (error === null || typeof error !== 'object') return false;

    const candidate = error as {
        readonly status?: unknown;
        readonly statusCode?: unknown;
        readonly response?: { readonly status?: unknown };
        readonly cause?: unknown;
    };

    return (
        candidate.status === 401 ||
        candidate.statusCode === 401 ||
        candidate.response?.status === 401 ||
        (candidate.cause !== undefined && isUnauthorizedError(candidate.cause))
    );
}

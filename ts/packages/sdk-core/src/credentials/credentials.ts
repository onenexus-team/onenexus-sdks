/**
 * Platform credential primitives.
 *
 * Mirrors the language-agnostic design in the repository `README.md`.
 * `AccessToken` is the data needed to call OneNexus APIs; `Credentials` is the
 * active interface every credential source implements.
 *
 * Design note: `expiresAt` is absolute, not a relative `expires_in`. Absolute timestamps
 *    are unambiguous across process restarts, log records, and clock
 *    observations; relative durations are not.
 */

/**
 * One CAS-issued access token. Immutable data; no behaviour, no network calls,
 * no refresh logic, and no grant metadata such as refresh token, ID token, or
 * scopes.
 */
export interface AccessToken {
    readonly accessToken: string;
    readonly tokenType: 'Bearer';
    readonly expiresAt: Date;
}

/**
 * Skew-aware clock used by credentials to decide token expiry.
 *
 * Transports observe server time from response headers; credentials read the
 * corrected clock when deciding whether a cached token is stale.
 */
export interface Clock {
    serverNow(): number;
    observeServerTime(serverDate: Date): void;
}

/**
 * Default clock backed by `Date.now()` plus the latest observed server delta.
 */
export class SystemClock implements Clock {
    private serverDeltaMs = 0;

    serverNow(): number {
        return Date.now() + this.serverDeltaMs;
    }

    observeServerTime(serverDate: Date): void {
        const serverTimeMs = serverDate.getTime();
        if (Number.isNaN(serverTimeMs)) return;

        this.serverDeltaMs = serverTimeMs - Date.now();
    }
}

/**
 * Per-client ambient state supplied to credential resolution.
 *
 * The transport owns this context, records observed server time into its clock,
 * and passes it to credentials on every resolve.
 */
export interface ClientContext {
    readonly clock: Clock;
    readonly refreshLeewayMs: number;
}

/**
 * Recoverable signal that a held token is stale by local expiry rules.
 *
 * Parent credential objects that compose another credential may catch this and
 * re-mint their own token. Top-level callers should treat it as requiring a new
 * credential value from the application.
 */
export class StaleCredentialsError extends Error {
    constructor(message = 'Credentials are stale.') {
        super(message);
        this.name = 'StaleCredentialsError';
    }
}

/**
 * Terminal authentication failure while refreshing or minting credentials.
 *
 * This is used when the auth server rejects the current credential source (for
 * example a revoked refresh token or client assertion). Retrying the same
 * credential source is not expected to recover.
 */
export class AuthenticationError extends Error {
    override readonly cause?: unknown;

    constructor(message = 'Authentication failed.', options?: { readonly cause?: unknown }) {
        super(message);
        this.name = 'AuthenticationError';
        this.cause = options?.cause;
    }
}

/**
 * A source of `AccessToken`. Active implementations cache, single-flight concurrent
 * refreshes, and honour cancellation. Static implementations just return their
 * held value.
 */
export interface Credentials {
    /**
     * Return an `AccessToken` value that is non-expired at the moment of the
     * call, using the supplied client context for expiry decisions.
     *
     * Implementations should refresh when the cached token is near expiry,
     * single-flight concurrent calls during refresh, and propagate
     * cancellation via the optional `AbortSignal`.
     *
     * @throws StaleCredentialsError when a held token is expired and this
     * credential cannot refresh it itself.
     * @throws AuthenticationError when a refresh or mint attempt is rejected by
     * the authentication authority.
     */
    resolve(context: ClientContext, signal?: AbortSignal): Promise<AccessToken>;
}

import ky, { type KyInstance, type Options as KyOptions } from 'ky';

import type { ClientContext, Credentials } from '../credentials/credentials.js';
import { AuthenticationError, StaleCredentialsError } from '../credentials/credentials.js';

const DEFAULT_RETRY_LIMIT = 2;
const DEFAULT_RETRY_BACKOFF_LIMIT_MS = 5_000;
const DEFAULT_RETRY_BASE_DELAY_MS = 300;

/**
 * Configuration for {@link createKy}.
 *
 * `baseUrl` becomes Ky's `prefixUrl`; generated client URLs are
 * relative paths that get joined against it at request time.
 *
 * `credentials` is hooked into the request lifecycle:
 * - `beforeRequest` resolves the credential and sets the `Authorization`
 *   header.
 * - `afterResponse` records the server `Date` header into the client context's
 *   clock so subsequent credential expiry checks account for clock skew.
 */
export interface CreateKyOptions {
    readonly baseUrl: string;
    readonly credentials: Credentials;
    readonly context: ClientContext;
    /** Per-request timeout in milliseconds. Defaults to 30_000. */
    readonly timeout?: number;
    /**
     * Retry configuration. Defaults: limit 2; methods include `post` because
     * the platform RPC surface is POST-only. Retry delay uses exponential
     * backoff with full jitter, capped by `backoffLimitMs`.
     */
    readonly retry?: {
        readonly limit?: number;
        readonly backoffLimitMs?: number;
    };
    /**
     * Additional Ky options merged in last. Escape hatch for advanced
     * consumers; prefer the named fields above where possible.
     */
    readonly extraOptions?: KyOptions;
}

/**
 * Build a Ky instance pre-wired with the platform auth + retry + timeout
 * conventions. Returned instance is what {@link createMutator}-equivalent
 * call sites pass through `options.http`.
 */
export function createKy(config: CreateKyOptions): KyInstance {
    const { baseUrl, credentials, context, timeout = 30_000, retry, extraOptions } = config;

    return ky.create({
        prefixUrl: baseUrl,
        timeout,
        retry: {
            limit: retry?.limit ?? DEFAULT_RETRY_LIMIT,
            // The CAS RPC surface is POST-only; default Ky retry methods omit
            // POST. We include the full set so retry behaviour works for every
            // operation regardless of method.
            methods: ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'],
            statusCodes: [401, 408, 429, 500, 502, 503, 504],
            backoffLimit: retry?.backoffLimitMs ?? DEFAULT_RETRY_BACKOFF_LIMIT_MS,
            delay: jitteredExponentialRetryDelay,
        },
        hooks: {
            beforeRequest: [
                async (request) => {
                    const token = await credentials.resolve(context, request.signal);
                    request.headers.set(
                        'Authorization',
                        `${token.tokenType} ${token.accessToken}`,
                    );
                },
            ],
            afterResponse: [
                (_request, _options, response) => {
                    observeServerDate(context, response);
                },
            ],
            beforeRetry: [
                ({ error }) => {
                    if (error instanceof AuthenticationError || error instanceof StaleCredentialsError) {
                        throw error;
                    }
                },
            ],
        },
        ...extraOptions,
    });
}

function jitteredExponentialRetryDelay(attemptCount: number): number {
    const exponentialDelayMs = DEFAULT_RETRY_BASE_DELAY_MS * 2 ** (attemptCount - 1);
    return Math.random() * exponentialDelayMs;
}

function observeServerDate(context: ClientContext, response: Response): void {
    const serverDateHeader = response.headers.get('date');
    if (serverDateHeader === null) return;

    context.clock.observeServerTime(new Date(serverDateHeader));
}

import type { KyInstance, Options as KyOptions } from 'ky';

import { parseHttpError } from './errors.js';

/**
 * The orval-facing mutator. Wraps Ky as the underlying HTTP transport, parses
 * RFC 9457 Problem Details into typed {@link PlatformError} subclasses on
 * failure, and surfaces successful responses as parsed JSON.
 *
 * Per-call state — specifically the {@link KyInstance} built by
 * {@link ClientBase} and carrying the consumer's credentials, baseUrl, context,
 * and retry policy — is passed in the second argument (the "options" slot
 * orval generates as `SecondParameter<typeof platformMutator>`). This is what
 * lets a single mutator function be shared across multiple concurrent
 * service-client instances.
 *
 * Service-client classes extend {@link ClientBase}; generated-operation calls
 * receive the base class' transport through `options.http`.
 */

/** Shape of the config object orval's `client: 'fetch'`/`'axios'` modes hand us. */
export interface PlatformMutatorRequestConfig {
    readonly url: string;
    readonly method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    readonly headers?: Record<string, string>;
    readonly params?: Record<string, unknown>;
    readonly data?: unknown;
    readonly signal?: AbortSignal;
}

/** Second-argument options carrying per-call instance state. */
export interface PlatformMutatorOptions {
    /** Ky instance from the owning service client. Required. */
    readonly http: KyInstance;
    /** Cancellation. Takes precedence over `config.signal` when both are set. */
    readonly signal?: AbortSignal;
}

/**
 * Serialise an orval `params` record into something Ky's `searchParams`
 * accepts. Skips `undefined`/`null` values; converts scalars (`string` |
 * `number` | `boolean` | `bigint`); spreads arrays into repeated
 * `?key=v1&key=v2` form. Object values are a programming error (they would
 * stringify to `[object Object]`) and trigger a thrown error so the call
 * site can correct the type.
 */
function toQueryString(value: unknown): string | undefined {
    if (value === undefined || value === null) return undefined;
    switch (typeof value) {
        case 'string':
            return value;
        case 'number':
        case 'boolean':
        case 'bigint':
            return value.toString();
        default:
            throw new TypeError(
                `platformMutator: query param value of type ${typeof value} is not serialisable. ` +
                    'Stringify or pre-serialise complex values at the call site.',
            );
    }
}

function serializeParams(params: Record<string, unknown> | undefined): URLSearchParams | undefined {
    if (params === undefined) return undefined;

    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (Array.isArray(value)) {
            for (const item of value as unknown[]) {
                const serialised = toQueryString(item);
                if (serialised !== undefined) search.append(key, serialised);
            }
        } else {
            const serialised = toQueryString(value);
            if (serialised !== undefined) search.append(key, serialised);
        }
    }
    return search;
}

export const platformMutator = async <T>(
    config: PlatformMutatorRequestConfig,
    options?: PlatformMutatorOptions,
): Promise<T> => {
    if (options?.http === undefined) {
        throw new Error(
            '@onenexus/sdk-core: platformMutator requires options.http. ' +
                'Ensure the service-client class passes its ClientBase transport via ' +
                'the second argument of every generated operation.',
        );
    }

    // Ky's prefixUrl resolution rejects URLs that start with '/'.
    const relativeUrl = config.url.startsWith('/') ? config.url.slice(1) : config.url;

    const init: KyOptions = { method: config.method };

    const effectiveSignal = options.signal ?? config.signal;
    if (effectiveSignal !== undefined) {
        init.signal = effectiveSignal;
    }
    if (config.headers !== undefined) {
        init.headers = config.headers;
    }
    const searchParams = serializeParams(config.params);
    if (searchParams !== undefined) {
        init.searchParams = searchParams;
    }
    if (config.data !== undefined) {
        init.json = config.data;
    }

    let response: Response;
    try {
        response = await options.http(relativeUrl, init);
    } catch (error) {
        throw await parseHttpError(error);
    }

    if (response.status === 204 || response.headers.get('content-length') === '0') {
        return undefined as T;
    }

    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
        return (await response.json()) as T;
    }

    // Fallback for unexpected content types — return as text. Generated code
    // typed against `T` will see this as a runtime mismatch if it relied on a
    // JSON shape; that's the caller's bug to diagnose, not the SDK's job to
    // mask.
    return (await response.text()) as unknown as T;
};

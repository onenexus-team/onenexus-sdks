import type { ClientContext, Credentials } from './credentials/credentials.js';
import { SystemClock } from './credentials/credentials.js';
import { createKy, type CreateKyOptions } from './http/ky-client.js';
import type { PlatformMutatorOptions } from './http/mutator.js';

const DEFAULT_REFRESH_LEEWAY_MS = 30_000;

/** Shared construction fields for generated service clients. */
export interface ClientBaseConfig {
    readonly baseUrl: string;
    readonly credentials: Credentials;
    readonly context?: ClientContext;
    /** Preemptive credential refresh window in milliseconds. Defaults to 30_000. */
    readonly refreshLeewayMs?: number;
    /** Per-request timeout in milliseconds. Defaults to 30_000 (see `createKy`). */
    readonly timeout?: number;
    /** Retry policy overrides. Defaults to 2 retries (see `createKy`). */
    readonly retry?: CreateKyOptions['retry'];
    /** Advanced Ky options merged by `createKy`. */
    readonly extraOptions?: CreateKyOptions['extraOptions'];
}

/**
 * Base class for generated OneNexus service clients.
 *
 * Owns the per-client context (including the skew-aware clock), builds the
 * shared Ky transport, and creates the mutator options passed into generated
 * operation functions.
 */
export abstract class ClientBase {
    protected readonly context: ClientContext;
    protected readonly http: ReturnType<typeof createKy>;

    protected constructor(config: ClientBaseConfig) {
        this.context = {
            ...(config.context ?? {
                clock: new SystemClock(),
                refreshLeewayMs: DEFAULT_REFRESH_LEEWAY_MS,
            }),
            refreshLeewayMs:
                config.refreshLeewayMs ?? config.context?.refreshLeewayMs ?? DEFAULT_REFRESH_LEEWAY_MS,
        };
        this.http = createKy({
            baseUrl: config.baseUrl,
            credentials: config.credentials,
            context: this.context,
            ...(config.timeout !== undefined && { timeout: config.timeout }),
            ...(config.retry !== undefined && { retry: config.retry }),
            ...(config.extraOptions !== undefined && { extraOptions: config.extraOptions }),
        });
    }

    protected mutatorOptions(options?: { readonly signal?: AbortSignal }): PlatformMutatorOptions {
        return options?.signal !== undefined
            ? { http: this.http, signal: options.signal }
            : { http: this.http };
    }
}
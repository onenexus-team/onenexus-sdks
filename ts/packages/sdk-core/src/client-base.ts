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
    protected readonly baseUrl: string;
    protected readonly credentials: Credentials;
    protected readonly context: ClientContext;
    protected readonly http: ReturnType<typeof createKy>;
    private readonly timeout: number | undefined;
    private readonly retry: CreateKyOptions['retry'];
    private readonly extraOptions: CreateKyOptions['extraOptions'];

    protected constructor(config: ClientBaseConfig) {
        this.baseUrl = config.baseUrl;
        this.credentials = config.credentials;
        this.timeout = config.timeout;
        this.retry = config.retry;
        this.extraOptions = config.extraOptions;
        this.context = {
            ...(config.context ?? {
                clock: new SystemClock(),
                refreshLeewayMs: DEFAULT_REFRESH_LEEWAY_MS,
            }),
            refreshLeewayMs:
                config.refreshLeewayMs ?? config.context?.refreshLeewayMs ?? DEFAULT_REFRESH_LEEWAY_MS,
        };
        this.http = this.createHttp(this.baseUrl, this.credentials);
    }

    protected createHttp(
        baseUrl: string,
        credentials: Credentials,
        nonRetryableStatusCodes?: readonly number[],
    ): ReturnType<typeof createKy> {
        return createKy({
            baseUrl,
            credentials,
            context: this.context,
            ...(this.timeout !== undefined && { timeout: this.timeout }),
            ...(this.retry !== undefined && { retry: this.retry }),
            ...(nonRetryableStatusCodes !== undefined && { nonRetryableStatusCodes }),
            ...(this.extraOptions !== undefined && { extraOptions: this.extraOptions }),
        });
    }

    protected mutatorOptions(
        options?: { readonly signal?: AbortSignal },
        http: ReturnType<typeof createKy> = this.http,
    ): PlatformMutatorOptions {
        return options?.signal !== undefined ? { http, signal: options.signal } : { http };
    }
}
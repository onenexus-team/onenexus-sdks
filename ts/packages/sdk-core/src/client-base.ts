import type { RequestAdapter, RequestConfiguration } from '@microsoft/kiota-abstractions';

import type { ClientContext, Credentials } from './credentials/credentials.js';
import { SystemClock } from './credentials/credentials.js';
import {
    createRequestAdapter,
    createRequestConfiguration,
    normalizeKiotaValue,
    type ClientRequestOptions,
    type KiotaRetryConfig,
} from './http/request-adapter.js';

const DEFAULT_REFRESH_LEEWAY_MS = 30_000;

/** Shared construction fields for generated service clients. */
export interface ClientBaseConfig {
    readonly baseUrl: string;
    readonly credentials: Credentials;
    readonly context?: ClientContext;
    /** Preemptive credential refresh window in milliseconds. Defaults to 30_000. */
    readonly refreshLeewayMs?: number;
    /** Per-attempt timeout in milliseconds. Set to 0 to disable. Defaults to 30_000. */
    readonly timeout?: number;
    /** Native Kiota retry policy overrides. */
    readonly retry?: KiotaRetryConfig;
}

/**
 * Base class for OneNexus service facades backed by generated Kiota clients.
 *
 * Owns the skew-aware context and one isolated request adapter per facade
 * instance. Generated request builders remain private implementation details.
 */
export abstract class ClientBase {
    protected readonly context: ClientContext;
    protected readonly requestAdapter: RequestAdapter;

    protected constructor(config: ClientBaseConfig) {
        this.context = {
            ...(config.context ?? {
                clock: new SystemClock(),
                refreshLeewayMs: DEFAULT_REFRESH_LEEWAY_MS,
            }),
            refreshLeewayMs:
                config.refreshLeewayMs ??
                config.context?.refreshLeewayMs ??
                DEFAULT_REFRESH_LEEWAY_MS,
        };
        this.requestAdapter = createRequestAdapter({
            baseUrl: config.baseUrl,
            credentials: config.credentials,
            context: this.context,
            ...(config.timeout !== undefined && { timeout: config.timeout }),
            ...(config.retry !== undefined && { retry: config.retry }),
        });
    }

    protected requestConfiguration(
        body: unknown,
        options?: ClientRequestOptions,
    ): RequestConfiguration<object> {
        return createRequestConfiguration(body, options);
    }

    protected async expectResponse<T>(response: Promise<T | undefined>): Promise<T> {
        const value = await response;
        if (value === undefined) {
            throw new Error(
                'The service returned no response body for an operation that requires one.',
            );
        }
        return normalizeKiotaValue(value) as T;
    }

    protected async expectNoResponse(response: Promise<unknown>): Promise<void> {
        await response;
    }
}

export type { ClientRequestOptions } from './http/request-adapter.js';

import {
    AllowedHostsValidator,
    type AuthenticationProvider,
    type RequestAdapter,
    type RequestConfiguration,
    isUntypedNode,
    type RequestInformation,
    type RequestOption,
} from '@microsoft/kiota-abstractions';
import {
    FetchRequestAdapter,
    KiotaClientFactory,
    MiddlewareFactory,
    RetryHandler,
    RetryHandlerOptions,
    type Middleware,
} from '@microsoft/kiota-http-fetchlibrary';

import type { ClientContext, Credentials } from '../credentials/credentials.js';
import { parseHttpResponseError } from './errors.js';

const DEFAULT_RETRY_LIMIT = 2;
const DEFAULT_RETRY_DELAY_MS = 300;
const DEFAULT_TIMEOUT_MS = 30_000;
const REQUEST_OPTION_KEY = 'OneNexusRequestOption';

/** Per-call controls shared by every OneNexus service facade. */
export interface ClientRequestOptions {
    readonly signal?: AbortSignal;
}

/** Native Kiota retry controls exposed by OneNexus clients. */
export interface KiotaRetryConfig {
    /** Number of retries after the initial request. Defaults to 2; Kiota allows at most 10. */
    readonly limit?: number;
    /**
     * Compatibility field from the previous transport. Kiota has a fixed
     * 180-second maximum delay, so this can only cap the initial 300 ms delay.
     */
    readonly backoffLimitMs?: number;
}

/** Construction options for {@link createRequestAdapter}. */
export interface CreateRequestAdapterOptions {
    readonly baseUrl: string;
    readonly credentials: Credentials;
    readonly context: ClientContext;
    /** Per-attempt timeout in milliseconds. Set to 0 to disable. Defaults to 30_000. */
    readonly timeout?: number;
    readonly retry?: KiotaRetryConfig;
}

class OneNexusRequestOption implements RequestOption {
    constructor(
        readonly body: unknown,
        readonly signal: AbortSignal | undefined,
    ) {}

    getKey(): string {
        return REQUEST_OPTION_KEY;
    }
}

function getOneNexusRequestOption(
    requestOptions: Record<string, RequestOption> | undefined,
): OneNexusRequestOption | undefined {
    const option = requestOptions?.[REQUEST_OPTION_KEY];
    return option instanceof OneNexusRequestOption ? option : undefined;
}

/** Convert Kiota untyped wrappers into ordinary JSON-compatible values. */
export function normalizeKiotaValue(value: unknown): unknown {
    if (isUntypedNode(value)) return normalizeKiotaValue(value.getValue());
    if (Array.isArray(value)) return value.map(normalizeKiotaValue);
    if (value instanceof Date) return value;
    if (value !== null && typeof value === 'object') {
        return Object.fromEntries(
            Object.entries(value).map(([key, child]) => [key, normalizeKiotaValue(child)]),
        );
    }
    return value;
}

/**
 * Bridges the OneNexus credential contract to Kiota while preventing bearer
 * tokens from being sent to any host other than the configured service host.
 */
export class OneNexusAuthenticationProvider implements AuthenticationProvider {
    readonly allowedHostsValidator: AllowedHostsValidator;

    constructor(
        private readonly credentials: Credentials,
        private readonly context: ClientContext,
        allowedHost: string,
    ) {
        this.allowedHostsValidator = new AllowedHostsValidator(new Set([allowedHost]));
    }

    async authenticateRequest(request: RequestInformation): Promise<void> {
        const url = request.URL;
        if (!this.allowedHostsValidator.isUrlHostValid(url)) {
            throw new Error(`Refusing to authenticate a request to a non-allowed host: ${url}`);
        }

        const option = getOneNexusRequestOption(request.getRequestOptions());
        const token = await this.credentials.resolve(this.context, option?.signal);
        request.headers.delete('Authorization');
        request.headers.add('Authorization', `${token.tokenType} ${token.accessToken}`);
    }
}

class RequestControlMiddleware implements Middleware {
    next: Middleware | undefined;

    constructor(private readonly timeout: number) {}

    async execute(
        url: string,
        requestInit: RequestInit,
        requestOptions?: Record<string, RequestOption>,
    ): Promise<Response> {
        if (this.next === undefined) {
            throw new Error('RequestControlMiddleware must have a next middleware.');
        }

        const option = getOneNexusRequestOption(requestOptions);
        if (option !== undefined) {
            // Preserve facade wire compatibility for free-form JSON schemas that
            // Kiota cannot serialize when additional-data generation is disabled.
            requestInit.body = JSON.stringify(normalizeKiotaValue(option.body));
        }

        const signals: AbortSignal[] = [];
        if (option?.signal !== undefined) signals.push(option.signal);
        if (this.timeout > 0) signals.push(AbortSignal.timeout(this.timeout));
        if (signals.length === 1) requestInit.signal = signals[0]!;
        if (signals.length > 1) requestInit.signal = AbortSignal.any(signals);

        return this.next.execute(url, requestInit, requestOptions);
    }
}

class DateHeaderObservationMiddleware implements Middleware {
    next: Middleware | undefined;

    constructor(private readonly context: ClientContext) {}

    async execute(
        url: string,
        requestInit: RequestInit,
        requestOptions?: Record<string, RequestOption>,
    ): Promise<Response> {
        if (this.next === undefined) {
            throw new Error('DateHeaderObservationMiddleware must have a next middleware.');
        }

        const response = await this.next.execute(url, requestInit, requestOptions);
        const rawDate = response.headers.get('date');
        if (rawDate !== null) {
            const serverDate = new Date(rawDate);
            if (!Number.isNaN(serverDate.getTime())) {
                this.context.clock.observeServerTime(serverDate);
            }
        }
        return response;
    }
}

class PlatformErrorMiddleware implements Middleware {
    next: Middleware | undefined;

    async execute(
        url: string,
        requestInit: RequestInit,
        requestOptions?: Record<string, RequestOption>,
    ): Promise<Response> {
        if (this.next === undefined) {
            throw new Error('PlatformErrorMiddleware must have a next middleware.');
        }

        const response = await this.next.execute(url, requestInit, requestOptions);
        const platformError = await parseHttpResponseError(response);
        if (platformError !== undefined) throw platformError;
        return response;
    }
}

function normalizeBaseUrl(baseUrl: string): URL {
    const parsed = new URL(baseUrl);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        throw new TypeError('baseUrl must use the http or https protocol.');
    }
    if (parsed.username !== '' || parsed.password !== '') {
        throw new TypeError('baseUrl must not contain credentials.');
    }
    parsed.pathname = parsed.pathname.replace(/\/$/, '');
    parsed.search = '';
    parsed.hash = '';
    return parsed;
}

function createRetryHandler(config: KiotaRetryConfig | undefined): RetryHandler {
    const initialDelayMs = Math.min(
        DEFAULT_RETRY_DELAY_MS,
        config?.backoffLimitMs ?? DEFAULT_RETRY_DELAY_MS,
    );
    return new RetryHandler(
        new RetryHandlerOptions({
            delay: initialDelayMs / 1_000,
            maxRetries: config?.limit ?? DEFAULT_RETRY_LIMIT,
        }),
    );
}

/**
 * Constructs the fetch-backed Kiota request adapter used by service packages.
 *
 * The middleware order is intentional: Problem Details conversion wraps the
 * native retry handler, while Date observation and timeout/cancellation run on
 * every retry attempt.
 */
export function createRequestAdapter(config: CreateRequestAdapterOptions): RequestAdapter {
    const baseUrl = normalizeBaseUrl(config.baseUrl);
    const authenticationProvider = new OneNexusAuthenticationProvider(
        config.credentials,
        config.context,
        baseUrl.host,
    );

    const defaultMiddlewares = MiddlewareFactory.getDefaultMiddlewares().filter(
        (middleware) => !(middleware instanceof RetryHandler),
    );
    const middlewares: Middleware[] = [
        new PlatformErrorMiddleware(),
        createRetryHandler(config.retry),
        new RequestControlMiddleware(config.timeout ?? DEFAULT_TIMEOUT_MS),
        new DateHeaderObservationMiddleware(config.context),
        ...defaultMiddlewares,
    ];

    const adapter = new FetchRequestAdapter(
        authenticationProvider,
        undefined,
        undefined,
        KiotaClientFactory.create(undefined, middlewares),
    );
    adapter.baseUrl = baseUrl.toString().replace(/\/$/, '');
    return adapter;
}

/** Internal bridge from flat facade options to generated Kiota request configuration. */
export function createRequestConfiguration(
    body: unknown,
    options?: ClientRequestOptions,
): RequestConfiguration<object> {
    return {
        options: [new OneNexusRequestOption(body, options?.signal)],
    };
}

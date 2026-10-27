import { AsyncLocalStorage } from 'node:async_hooks';
import { randomBytes } from 'node:crypto';
import {
    context,
    trace,
    ROOT_CONTEXT,
    isSpanContextValid,
    type SpanContext,
} from '@opentelemetry/api';

export type HeaderEntries = Iterable<readonly [string, string | readonly string[] | undefined]>;
export interface IncomingOptions {
    trusted: boolean;
    preserveSampling?: boolean;
}
const current = new AsyncLocalStorage<Readonly<{ value: SpanContext | undefined }>>();

function parse(headers: HeaderEntries, options: IncomingOptions): SpanContext | undefined {
    if (options.trusted !== true) return undefined;
    let candidate: string | undefined;
    for (const [key, value] of headers) {
        if (key.toLowerCase() !== 'traceparent') continue;
        if (candidate !== undefined || typeof value !== 'string') return undefined;
        candidate = value;
    }
    if (
        !candidate ||
        candidate.length !== 55 ||
        !/^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$/.test(candidate)
    )
        return undefined;
    const value: SpanContext = {
        traceId: candidate.slice(3, 35),
        spanId: candidate.slice(36, 52),
        traceFlags: options.preserveSampling === false ? 0 : parseInt(candidate.slice(53), 16) & 1,
        isRemote: true,
    };
    return isSpanContextValid(value) ? value : undefined;
}

function run<T>(value: SpanContext | undefined, fn: () => T): T {
    // OTel integration is active only if the application has installed a context manager.
    // ALS provides phase-1 isolation without installing global instrumentation.
    const otel = value ? trace.setSpanContext(ROOT_CONTEXT, value) : ROOT_CONTEXT;
    return current.run(Object.freeze({ value }), () => context.with(otel, fn));
}

/** Boundary only. Trust is application policy, never derived from a request header. */
export function withIncomingContext<T>(
    headers: HeaderEntries,
    options: IncomingOptions,
    fn: () => T,
): T {
    return run(parse(headers, options), fn);
}

/** Independent system work must not inherit an unrelated request. */
export function withUncorrelatedContext<T>(fn: () => T): T {
    return run(undefined, fn);
}

/** Explicit edge policy for gateways/shared contract tests. Business services must use withIncomingContext. */
export function withEdgeContext<T>(
    headers: HeaderEntries,
    options: IncomingOptions,
    fn: () => T,
): T {
    return run(
        parse(headers, { ...options, preserveSampling: options.preserveSampling ?? false }) ?? {
            traceId: randomBytes(16).toString('hex'),
            spanId: randomBytes(8).toString('hex'),
            traceFlags: 0,
        },
        fn,
    );
}

function active(): SpanContext | undefined {
    const frame = current.getStore();
    const span = trace.getSpanContext(context.active());
    const valid = span && isSpanContextValid(span) ? span : undefined;
    if (!frame) return valid;
    if (!frame.value) return undefined;
    return valid?.traceId === frame.value.traceId ? valid : frame.value;
}

export function currentTraceId(): string | undefined {
    return active()?.traceId;
}

/** Snapshot for an HTTP call or job metadata. No baggage, credentials or tracestate. */
export function outgoingHeaders(): Record<string, string> {
    const value = active();
    return value
        ? {
              traceparent: `00-${value.traceId}-${value.spanId}-${value.traceFlags & 1 ? '01' : '00'}`,
          }
        : {};
}

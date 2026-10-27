import { afterEach, describe, expect, it } from 'vitest';
import { context, trace, ROOT_CONTEXT } from '@opentelemetry/api';
import { AsyncLocalStorageContextManager } from '@opentelemetry/context-async-hooks';
import {
    TracerProvider,
    SimpleSpanProcessor,
    InMemorySpanExporter,
} from '@opentelemetry/sdk-trace';
import { writeFileSync } from 'node:fs';
import {
    loadContract,
    validateRecord,
    CONTRACT_VERSION,
    CONTRACT_DIGEST,
} from '@onenexus-team/log-contract';
import {
    currentTraceId,
    outgoingHeaders,
    withIncomingContext,
    withUncorrelatedContext,
    withEdgeContext,
} from '@onenexus-team/observability';

const traceA = '11111111111111111111111111111111';
const traceB = '33333333333333333333333333333333';
const parent = `00-${traceA}-2222222222222222-01`;
const headers = [['traceparent', parent]] as const;
afterEach(() => {
    context.disable();
    trace.disable();
});

describe('context lifecycle', () => {
    it('runs all shared vectors through the actual runtime APIs', () => {
        const { vectors } = loadContract();
        const results: object[] = vectors.record_cases.map(
            (c: { id: string; record: unknown; profile: string }) => ({
                kind: 'record',
                id: c.id,
                errors: validateRecord(c.record, c.profile),
            }),
        );
        for (const item of vectors.context_cases) {
            const observed = withEdgeContext(
                [['traceparent', item.traceparent]],
                { trusted: item.trusted },
                () => ({
                    trace_id: currentTraceId(),
                    outgoing_traceparent: outgoingHeaders().traceparent,
                }),
            );
            expect(observed.trace_id).toMatch(/^[a-f0-9]{32}$/);
            expect(observed.outgoing_traceparent).toMatch(/-00$/);
            if (item.preserve_trace) expect(observed.trace_id).toBe(traceA);
            else expect(observed.trace_id).not.toBe(traceA);
            results.push({
                kind: 'context',
                id: item.id,
                ...observed,
                after_trace_id: currentTraceId() ?? null,
            });
        }
        expect(results).toHaveLength(66);
        if (process.env.ONENEXUS_CONTRACT_RESULTS)
            writeFileSync(
                process.env.ONENEXUS_CONTRACT_RESULTS,
                JSON.stringify({
                    adapter_protocol: 1,
                    contract_version: CONTRACT_VERSION,
                    contract_sha256: CONTRACT_DIGEST,
                    results,
                }),
            );
    });

    it('does not generate a service trace for missing, invalid, untrusted or duplicate headers', () => {
        for (const input of [
            [],
            [['traceparent', 'bad']],
            [
                ['traceparent', parent],
                ['TraceParent', parent],
            ],
            [['traceparent', [parent]]],
            [['traceparent', `00-${'0'.repeat(32)}-2222222222222222-01`]],
            [['traceparent', parent + '\n']],
        ]) {
            withIncomingContext(input as [string, string | string[]][], { trusted: true }, () => {
                expect(currentTraceId()).toBeUndefined();
                expect(outgoingHeaders()).toEqual({});
            });
        }
        withIncomingContext(headers, { trusted: false }, () =>
            expect(currentTraceId()).toBeUndefined(),
        );
        withIncomingContext(
            [
                ['TraceParent', parent],
                ['baggage', 'secret'],
                ['tracestate', 'secret'],
            ],
            { trusted: true },
            () => expect(outgoingHeaders()).toEqual({ traceparent: parent }),
        );
        withIncomingContext(headers, { trusted: true, preserveSampling: false }, () =>
            expect(outgoingHeaders().traceparent).toBe(parent.slice(0, -2) + '00'),
        );
    });

    it('concurrent_context_isolation, cancellation and reused_worker_context with barriers', async () => {
        const a = Promise.withResolvers<void>();
        const b = Promise.withResolvers<void>();
        await Promise.all([
            withIncomingContext(headers, { trusted: true }, async () => {
                a.resolve();
                await b.promise;
                expect(currentTraceId()).toBe(traceA);
                expect(() =>
                    withUncorrelatedContext(() => {
                        expect(currentTraceId()).toBeUndefined();
                        throw Error('cancelled');
                    }),
                ).toThrow('cancelled');
                expect(currentTraceId()).toBe(traceA);
            }),
            withIncomingContext(
                [['traceparent', parent.replace(traceA, traceB)]],
                { trusted: true },
                async () => {
                    await a.promise;
                    expect(currentTraceId()).toBe(traceB);
                    b.resolve();
                },
            ),
        ]);
        expect(currentTraceId()).toBeUndefined();
        await expect(
            withIncomingContext(headers, { trusted: true }, async () => {
                await Promise.resolve();
                throw new DOMException('cancelled', 'AbortError');
            }),
        ).rejects.toThrow('cancelled');
        expect(currentTraceId()).toBeUndefined();
        withIncomingContext([], { trusted: true }, () => expect(currentTraceId()).toBeUndefined());
    });

    it('durable_metadata_roundtrip preserves identity and clears legacy work', async () => {
        const saved = withIncomingContext(headers, { trusted: true }, () =>
            JSON.stringify(outgoingHeaders()),
        );
        for (let attempt = 1; attempt <= 2; attempt++) {
            await withIncomingContext(
                Object.entries(JSON.parse(saved) as Record<string, string>),
                { trusted: true },
                async () => {
                    await Promise.resolve();
                    expect(currentTraceId()).toBe(traceA);
                },
            );
            expect(currentTraceId()).toBeUndefined();
        }
        withUncorrelatedContext(() => expect(outgoingHeaders()).toEqual({}));
    });

    it('phase2_recorded_child_compatibility uses a real OTel recorded child', async () => {
        const manager = new AsyncLocalStorageContextManager().enable();
        context.setGlobalContextManager(manager);
        const exporter = new InMemorySpanExporter();
        const provider = new TracerProvider({
            spanProcessors: [new SimpleSpanProcessor({ exporter })],
        });
        const tracer = provider.getTracer('compatibility-test');
        await withIncomingContext(headers, { trusted: true }, async () => {
            const child = tracer.startSpan('future-child');
            await context.with(trace.setSpan(context.active(), child), async () => {
                await Promise.resolve();
                expect(currentTraceId()).toBe(traceA);
                expect(outgoingHeaders().traceparent).toContain(child.spanContext().spanId);
                withIncomingContext(headers, { trusted: true }, () => {
                    expect(outgoingHeaders().traceparent).toContain(child.spanContext().spanId);
                    expect(trace.getSpan(context.active())).toBe(child);
                });
                withUncorrelatedContext(() =>
                    context.with(trace.setSpan(ROOT_CONTEXT, child), () =>
                        expect(currentTraceId()).toBeUndefined(),
                    ),
                );
            });
            child.end();
            expect(outgoingHeaders().traceparent).toBe(parent);
            const unrelated = tracer.startSpan('unrelated', {}, ROOT_CONTEXT);
            context.with(trace.setSpan(ROOT_CONTEXT, unrelated), () =>
                expect(currentTraceId()).toBe(traceA),
            );
            unrelated.end();
        });
        await provider.forceFlush();
        expect(
            exporter
                .getFinishedSpans()
                .find((s) => s.name === 'future-child')
                ?.spanContext().traceId,
        ).toBe(traceA);
        await provider.shutdown();
        manager.disable();
    });
});

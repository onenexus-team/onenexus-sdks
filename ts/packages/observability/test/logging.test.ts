import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Writable } from 'node:stream';
import { setImmediate as nextTurn } from 'node:timers/promises';
import { expect, it } from 'vitest';
import {
    QUEUE_CAPACITY,
    createLogger,
    type LogFields,
    parseRecord,
    validateRecord,
    withIncomingContext,
} from '@onenexus-team/observability';
const config = {
    service: 'utility',
    environment: 'development' as const,
    region: 'ric1',
    allowedFields: ['job.attempt'],
};

it('emits common fields, message, events and exact timestamp; system events are uncorrelated', async () => {
    const lines: string[] = [];
    const stream = new Writable({
        write(chunk: Buffer, _encoding, cb) {
            lines.push(chunk.toString());
            cb();
        },
    });
    const logger = createLogger(config, stream);
    expect(logger.log('System ready', { event: 'system.ready', outcome: 'success' })).toBe(true);
    withIncomingContext(
        [['traceparent', '00-11111111111111111111111111111111-2222222222222222-01']],
        { trusted: true },
        () => {
            for (const level of ['TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL'] as const)
                expect(
                    logger.log('Work completed', {
                        level,
                        event: 'work.completed',
                        outcome: 'success',
                        fields: { 'job.attempt': 1 },
                    }),
                ).toBe(true);
        },
    );
    expect(await logger.close()).toBe(true);
    const rows = lines.map((s) => parseRecord(s) as Record<string, unknown>);
    expect(rows).toHaveLength(7);
    expect(rows[0]).not.toHaveProperty('trace_id');
    for (const row of rows) expect(validateRecord(row)).toEqual([]);
    expect(rows[1]?.trace_id).toBe('11111111111111111111111111111111');
    expect(typeof rows[1]?.timestamp).toBe('bigint');
    expect(logger.stats().written).toBe(7);
    expect(logger.log('After close')).toBe(false);
    expect(logger.stats().closed).toBe(1);
    await nextTurn();
    expect(stream.listenerCount('error')).toBe(0);
    expect(stream.writable).toBe(true);
});

it('fails bad configuration at startup; keeps degraded lines and drops only invalid ones, without echoing secrets', async () => {
    expect(() => createLogger({ ...config, region: '' })).toThrow();
    for (const allowedFields of [
        ['trace_id'],
        ['message'],
        ['__proto__'],
        ['logging.truncated'],
        Array.from({ length: 257 }, (_, i) => `example.f${i}`),
    ])
        expect(() => createLogger({ ...config, allowedFields })).toThrow('invalid_allowed_fields');
    const lines: string[] = [];
    const stream = new Writable({
        write(chunk: Buffer, _encoding, cb) {
            lines.push(chunk.toString());
            cb();
        },
    });
    const logger = createLogger(config, stream);
    // Kept and flagged: unknown, protected, non-finite, accessor and non-scalar fields are removed.
    expect(logger.log('safe', { fields: { authorization: 'secret-sentinel' } })).toBe(true);
    expect(logger.log('safe', { fields: { environment: 'prod', 'job.attempt': 1 } })).toBe(true);
    expect(logger.log('x'.repeat(1025))).toBe(true);
    expect(logger.log('safe', { fields: { 'job.attempt': NaN } })).toBe(true);
    expect(
        logger.log('safe', {
            fields: Object.defineProperty({}, 'job.attempt', {
                enumerable: true,
                get() {
                    throw Error('secret-sentinel');
                },
            }),
        }),
    ).toBe(true);
    expect(
        logger.log('safe', {
            fields: { 'job.attempt': ['secret-sentinel'] } as unknown as LogFields,
        }),
    ).toBe(true);
    // Still invalid: bad message, event or fields argument.
    expect(logger.log('')).toBe(false);
    expect(logger.log(42 as unknown as string)).toBe(false);
    expect(logger.log('safe', { event: 'x'.repeat(4097) })).toBe(false);
    expect(logger.log('safe', { fields: new Map() as unknown as LogFields })).toBe(false);
    expect(logger.stats().invalid).toBe(4);
    await logger.close();
    const rows = lines.map((s) => parseRecord(s) as Record<string, unknown>);
    expect(rows).toHaveLength(6);
    for (const row of rows) expect(validateRecord(row)).toEqual([]);
    expect(rows.map((r) => r['logging.dropped_field_count'])).toEqual([1, 1, undefined, 1, 1, 1]);
    expect(rows[1]).toMatchObject({ environment: 'development', 'job.attempt': 1 });
    expect(rows[2]).toMatchObject({ 'logging.truncated': true });
    expect(Buffer.byteLength(rows[2]!.message as string)).toBeLessThanOrEqual(1024);
    expect(lines.join('')).not.toContain('secret-sentinel');
});

it('backpressure queues lines, drops only when the queue is full, and writes the queue on drain', async () => {
    const callbacks: (() => void)[] = [];
    let open = false;
    const stream = new Writable({
        highWaterMark: 1,
        write(_chunk, _encoding, cb) {
            if (open) cb();
            else callbacks.push(() => cb());
        },
    });
    const logger = createLogger(config, stream);
    expect(logger.log('first')).toBe(true); // handed to the stream, which reports back-pressure
    for (let i = 0; i < QUEUE_CAPACITY; i++) expect(logger.log('queued')).toBe(true);
    for (let i = 0; i < 100; i++) expect(logger.log('overload')).toBe(false);
    expect(logger.stats()).toMatchObject({ pending: QUEUE_CAPACITY + 1, backpressure: 100, written: 0 });
    expect(await logger.flush(0)).toBe(false);
    open = true;
    callbacks.shift()?.();
    expect(await logger.flush(5000)).toBe(true);
    expect(logger.stats()).toMatchObject({ pending: 0, written: QUEUE_CAPACITY + 1 });
    expect(logger.log('recovered')).toBe(true);
    const closing = logger.close(1000);
    expect(logger.close()).toBe(closing);
    expect(await closing).toBe(true);
    expect(logger.log('closed')).toBe(false);
    await nextTurn();
    expect(logger.stats()).toMatchObject({ written: QUEUE_CAPACITY + 2, closed: 1 });
    expect(stream.listenerCount('error')).toBe(0);
});

it('bounds in-flight and queued lines even if a stream has a very large buffer', async () => {
    const stream = new Writable({ highWaterMark: 1_000_000, write() {} });
    const logger = createLogger(config, stream);
    let accepted = 0;
    for (let i = 0; i < 2000; i++) if (logger.log('bounded')) accepted++;
    expect(accepted).toBe(128 + QUEUE_CAPACITY);
    expect(logger.stats()).toMatchObject({ pending: accepted, backpressure: 2000 - accepted });
    expect(await logger.close(0)).toBe(false);
    stream.destroy(new Error('sink-failed'));
    await nextTurn();
    expect(logger.stats()).toMatchObject({ pending: 0, io: accepted });
});

it('a Node stream that errors stays errored: the failure is counted, later lines count as io', async () => {
    const stream = new Writable({
        write(_chunk, _encoding, cb) {
            cb(new Error('secret-sentinel'));
        },
    });
    const logger = createLogger(config, stream);
    expect(logger.log('first')).toBe(true);
    expect(await logger.flush()).toBe(true); // nothing pending; the failure is counted, not hung
    await nextTurn();
    expect(stream.writable).toBe(false);
    expect(logger.log('second')).toBe(false);
    expect(logger.stats()).toMatchObject({ io: 2, written: 0, pending: 0 });
    expect(await logger.close()).toBe(true);
    await expect(logger.flush(-1)).rejects.toThrow('invalid_flush_timeout');
});

const scenarios = JSON.parse(readFileSync(process.env.ONENEXUS_LOGGING_SCENARIOS ?? resolve('../../../tests/logging/scenarios.json'), 'utf8')) as {
    emission_cases: {id:string; traceparent:string|null; message:string; expected:Record<string,unknown>; absent?:string[]}[];
};
for (const scenario of scenarios.emission_cases) {
    it('shared emission: ' + scenario.id, async () => {
        const lines: string[] = [];
        const stream = new Writable({write(chunk: Buffer, _encoding, cb) { lines.push(chunk.toString()); cb(); }});
        const logger = createLogger({service:'shared-test', environment:'development', region:'region-1'}, stream);
        withIncomingContext(scenario.traceparent ? [['traceparent', scenario.traceparent]] : [], {trusted:true}, () => {
            expect(logger.log(scenario.message)).toBe(true);
        });
        await logger.close();
        expect(lines).toHaveLength(1);
        const row = parseRecord(lines[0]!) as Record<string,unknown>;
        for (const [key,value] of Object.entries(scenario.expected)) expect(row[key]).toEqual(value);
        for (const key of scenario.absent ?? []) expect(row).not.toHaveProperty(key);
        expect(validateRecord(row)).toEqual([]);
    });
}

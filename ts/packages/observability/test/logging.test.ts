import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Writable } from 'node:stream';
import { setImmediate as nextTurn } from 'node:timers/promises';
import { expect, it } from 'vitest';
import {
    createLogger,
    parseRecord,
    validateRecord,
    withIncomingContext,
} from '@onenexus-team/observability';
const config = {
    service: 'utility',
    environment: 'development' as const,
    region: 'ric1',
    allowedFields: ['attempt'],
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
                        fields: { attempt: 1 },
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

it('fails bad configuration at startup and rejects unsafe records without echoing secrets', async () => {
    expect(() => createLogger({ ...config, region: '' })).toThrow();
    for (const allowedFields of [['trace_id'], ['message'], ['__proto__'], Array(33).fill('field')])
        expect(() => createLogger({ ...config, allowedFields })).toThrow('invalid_allowed_fields');
    const lines: string[] = [];
    const stream = new Writable({
        write(chunk: Buffer, _encoding, cb) {
            lines.push(chunk.toString());
            cb();
        },
    });
    const logger = createLogger(config, stream);
    expect(logger.log('safe', { fields: { authorization: 'secret-sentinel' } })).toBe(false);
    expect(logger.log('')).toBe(false);
    expect(logger.log('x'.repeat(1025))).toBe(false);
    expect(logger.log('safe', { event: 'x'.repeat(4097) })).toBe(false);
    expect(logger.log('safe', { fields: { attempt: NaN } })).toBe(false);
    expect(
        logger.log('safe', {
            fields: Object.defineProperty({}, 'attempt', {
                enumerable: true,
                get() {
                    throw Error('secret-sentinel');
                },
            }),
        }),
    ).toBe(false);
    expect(logger.stats().invalid).toBe(6);
    expect(lines).toEqual([]);
    await logger.close();
});

it('backpressure drops boundedly then recovers on drain; flush and close have deadlines', async () => {
    let release: (() => void) | undefined;
    const stream = new Writable({
        highWaterMark: 1,
        write(_chunk, _encoding, cb) {
            release = cb;
        },
    });
    const logger = createLogger(config, stream);
    expect(logger.log('first')).toBe(true);
    for (let i = 0; i < 1000; i++) expect(logger.log('overload')).toBe(false);
    expect(logger.stats()).toMatchObject({ pending: 1, backpressure: 1000 });
    expect(await logger.flush(0)).toBe(false);
    const drained = new Promise<void>((resolve) => stream.once('drain', resolve));
    release?.();
    await drained;
    expect(logger.log('recovered')).toBe(true);
    const closing = logger.close(0);
    expect(logger.close()).toBe(closing);
    expect(await closing).toBe(false);
    expect(logger.log('closed')).toBe(false);
    release?.();
    await nextTurn();
    expect(logger.stats().written).toBe(2);
    expect(stream.listenerCount('error')).toBe(0);
});

it('caps pending records even if a stream has a very large buffer', async () => {
    const stream = new Writable({ highWaterMark: 1_000_000, write() {} });
    const logger = createLogger(config, stream);
    for (let i = 0; i < 128; i++) expect(logger.log('bounded')).toBe(true);
    expect(logger.log('overflow')).toBe(false);
    expect(logger.stats().pending).toBe(128);
    expect(await logger.close(0)).toBe(false);
    stream.destroy(new Error('sink-failed'));
    await nextTurn();
    expect(logger.stats()).toMatchObject({ pending: 0, io: 128 });
});

it('sink callback errors fail closed without changing business flow or recursively logging', async () => {
    const stream = new Writable({
        write(_chunk, _encoding, cb) {
            cb(new Error('secret-sentinel'));
        },
    });
    const logger = createLogger(config, stream);
    logger.log('first');
    expect(await logger.flush()).toBe(false);
    await nextTurn();
    expect(logger.log('second')).toBe(false);
    expect(logger.stats().io).toBe(2);
    expect(await logger.close()).toBe(false);
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

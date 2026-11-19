// One drop metric (tests/logging/scenarios.json `drop_metric`, design review R1): every line
// a logger does not write is counted process-wide per (service, reason). The counter is
// module-level, so every test uses its own service names.
import { EventEmitter } from 'node:events';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Writable } from 'node:stream';
import { setImmediate as nextTurn } from 'node:timers/promises';
import type { Attributes, Meter, ObservableCallback, ObservableResult } from '@opentelemetry/api';
import { expect, it } from 'vitest';
import {
    createLogger,
    dropMetricsText,
    logDropCounts,
    registerDropMetric,
    type DropCount,
    type JsonLogger,
} from '@onenexus-team/observability';

const METRIC = (
    JSON.parse(
        readFileSync(
            process.env.ONENEXUS_LOGGING_SCENARIOS ??
                resolve('../../../tests/logging/scenarios.json'),
            'utf8',
        ),
    ) as {
        drop_metric: {
            otel_name: string;
            otel_unit: string;
            help: string;
            reasons: string[];
            prometheus_text_example: { counts: DropCount[]; text: string };
        };
    }
).drop_metric;
const configFor = (service: string) => ({
    service,
    environment: 'development' as const,
    region: 'region-1',
});
/** The service's rows as reason -> count. */
const rowsOf = (service: string) =>
    Object.fromEntries(
        logDropCounts()
            .filter((row) => row.service === service)
            .map((row) => [row.reason, row.count]),
    );
/** What the metric must equal: the sum of the loggers' own counters (shared names). */
const statsSum = (...loggers: JsonLogger[]) => {
    const sum = { closed: 0, invalid: 0, io_errors: 0, queue_full: 0 };
    for (const stats of loggers.map((logger) => logger.stats())) {
        sum.closed += stats.closed;
        sum.invalid += stats.invalid;
        sum.io_errors += stats.io;
        sum.queue_full += stats.backpressure;
    }
    return sum;
};

class Ok extends Writable {
    override _write(_chunk: Buffer, _encoding: BufferEncoding, cb: (error?: Error | null) => void) {
        cb();
    }
}
/** Accepts one write, then reports back-pressure and never acknowledges until released. */
class Gate extends Writable {
    private open = false;
    private held: (() => void)[] = [];
    constructor() {
        super({ highWaterMark: 1 });
    }
    override _write(_chunk: Buffer, _encoding: BufferEncoding, cb: (error?: Error | null) => void) {
        if (this.open) cb();
        else this.held.push(() => cb());
    }
    release() {
        this.open = true;
        for (const done of this.held.splice(0)) done();
    }
}
/** Fails its first write but stays writable. */
class FailFirst extends EventEmitter {
    readonly destroyed = false;
    readonly writable = true;
    readonly writableNeedDrain = false;
    private failed = false;
    write(_chunk: string, cb: (error?: Error | null) => void): boolean {
        const error = this.failed ? undefined : new Error('broken pipe');
        this.failed = true;
        process.nextTick(() => cb(error));
        return true;
    }
}

it('every_reason_reported_from_first_handler', async () => {
    expect(rowsOf('first-handler')).toEqual({});
    const logger = createLogger(configFor('first-handler'), new Ok());
    expect(logDropCounts().filter((row) => row.service === 'first-handler')).toEqual(
        METRIC.reasons.map((reason) => ({ service: 'first-handler', reason, count: 0 })),
    );
    await logger.close();
});

it('a rejected configuration registers no service', () => {
    expect(() => createLogger(configFor(''), new Ok())).toThrow();
    expect(logDropCounts().some((row) => row.service === '')).toBe(false);
});

it('each_reason_counted', async () => {
    const zero = { closed: 0, invalid: 0, io_errors: 0, queue_full: 0 };

    const invalid = createLogger(configFor('each-invalid'), new Ok());
    expect(invalid.log(42 as unknown as string)).toBe(false); // the contract rejects it
    expect(invalid.stats().invalid).toBe(1);
    expect(rowsOf('each-invalid')).toEqual({ ...zero, invalid: 1 });
    expect(rowsOf('each-invalid')).toEqual(statsSum(invalid));

    const io = createLogger(configFor('each-io'), new FailFirst() as unknown as Writable);
    io.log('line 0');
    io.log('line 1');
    expect(await io.flush()).toBe(true);
    expect(io.stats()).toMatchObject({ io: 1, written: 1 });
    expect(rowsOf('each-io')).toEqual({ ...zero, io_errors: 1 });
    expect(rowsOf('each-io')).toEqual(statsSum(io));

    const closed = createLogger(configFor('each-closed'), new Ok());
    expect(await closed.close()).toBe(true);
    expect(closed.log('too late')).toBe(false);
    expect(closed.stats().closed).toBe(1);
    expect(rowsOf('each-closed')).toEqual({ ...zero, closed: 1 });
    expect(rowsOf('each-closed')).toEqual(statsSum(closed));

    const stream = new Gate();
    const full = createLogger(configFor('each-full'), stream);
    for (let i = 0; i < 3000; i++) full.log(`line ${i}`);
    const overflow = full.stats().backpressure;
    expect(overflow).toBeGreaterThan(0);
    expect(rowsOf('each-full')).toEqual({ ...zero, queue_full: overflow });
    expect(rowsOf('each-full')).toEqual(statsSum(full));
    stream.release();
    expect(await full.close()).toBe(true);
    await invalid.close();
    await io.close();
});

it('handlers_of_one_service_are_summed', async () => {
    const a = createLogger(configFor('summed'), new Ok());
    const b = createLogger(configFor('summed'), new Ok());
    a.log(1 as unknown as string);
    b.log(2 as unknown as string);
    b.log(3 as unknown as string);
    await a.close();
    a.log('too late');
    expect(logDropCounts().filter((row) => row.service === 'summed')).toHaveLength(4);
    expect(rowsOf('summed')).toEqual({ closed: 1, invalid: 3, io_errors: 0, queue_full: 0 });
    expect(rowsOf('summed')).toEqual(statsSum(a, b));
    await b.close();
});

it('services_are_separate', async () => {
    const a = createLogger(configFor('separate-a'), new Ok());
    const b = createLogger(configFor('separate-b'), new Ok());
    a.log(1 as unknown as string);
    expect(rowsOf('separate-a')).toEqual(statsSum(a));
    expect(rowsOf('separate-a').invalid).toBe(1);
    expect(rowsOf('separate-b')).toEqual({ closed: 0, invalid: 0, io_errors: 0, queue_full: 0 });
    await a.close();
    await b.close();
});

it('counts_survive_close', async () => {
    const logger = createLogger(configFor('survive'), new Ok());
    logger.log(1 as unknown as string);
    await logger.close();
    logger.log('too late');
    await nextTurn();
    const after = rowsOf('survive');
    expect(after).toEqual({ closed: 1, invalid: 1, io_errors: 0, queue_full: 0 });
    // A new logger for the service keeps (never resets) the totals.
    const next = createLogger(configFor('survive'), new Ok());
    expect(rowsOf('survive')).toEqual(after);
    await next.close();
});

it('prometheus_text_format', () => {
    const example = METRIC.prometheus_text_example;
    expect(dropMetricsText(example.counts)).toBe(example.text);
    // Without counts it renders the live snapshot.
    const logger = createLogger(configFor('prometheus-live'), new Ok());
    const live = dropMetricsText();
    expect(live.startsWith(example.text.split('\n').slice(0, 2).join('\n') + '\n')).toBe(true);
    expect(live).toContain(
        'onenexus_log_records_dropped_total{service="prometheus-live",reason="queue_full"} 0\n',
    );
    expect(live).toBe(dropMetricsText(logDropCounts()));
    void logger.close();
});

it('otel_asynchronous_counter', async () => {
    const created: { name: string; options: unknown }[] = [];
    const callbacks: ObservableCallback[] = [];
    const meter = {
        createObservableCounter(name: string, options: unknown) {
            created.push({ name, options });
            return {
                addCallback: (cb: ObservableCallback) => callbacks.push(cb),
                removeCallback: () => undefined,
            };
        },
    } as unknown as Meter;
    const logger = createLogger(configFor('otel'), new Ok());
    logger.log(1 as unknown as string);
    const instrument = registerDropMetric(meter);
    expect(typeof instrument.addCallback).toBe('function');
    expect(created).toEqual([
        {
            name: METRIC.otel_name,
            options: { unit: METRIC.otel_unit, description: METRIC.help },
        },
    ]);
    expect(callbacks).toHaveLength(1);
    // One collection: one observation per snapshot row.
    const observed: { value: number; attributes: Attributes | undefined }[] = [];
    const result: ObservableResult = {
        observe: (value, attributes) => observed.push({ value, attributes }),
    };
    await callbacks[0]!(result);
    expect(observed).toEqual(
        logDropCounts().map(({ service, reason, count }) => ({
            value: count,
            attributes: { service, reason },
        })),
    );
    expect(observed).toContainEqual({
        value: 1,
        attributes: { service: 'otel', reason: 'invalid' },
    });
    await logger.close();
});

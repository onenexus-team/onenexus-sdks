// The shared write model (tests/logging/scenarios.json `write_model`, design review F2):
// the caller never waits on the output; a bounded queue feeds the stream; a full queue
// drops and counts; a write error is counted and later lines are still written; close
// drains until a deadline.
import { EventEmitter } from 'node:events';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Writable } from 'node:stream';
import { performance } from 'node:perf_hooks';
import { setImmediate as nextTurn } from 'node:timers/promises';
import { expect, it } from 'vitest';
import {
    CLOSE_TIMEOUT_MS,
    QUEUE_CAPACITY,
    createLogger,
    parseRecord,
} from '@onenexus-team/observability';

interface Case {
    id: string;
    lines: number;
    languages: string[];
}
const MODEL = (
    JSON.parse(
        readFileSync(
            process.env.ONENEXUS_LOGGING_SCENARIOS ?? resolve('../../../tests/logging/scenarios.json'),
            'utf8',
        ),
    ) as {
        write_model: {
            queue_capacity: number;
            close_timeout_ms: number;
            caller_budget_ms: number;
            counters: string[];
            cases: Case[];
        };
    }
).write_model;
const CASES = new Map(MODEL.cases.map((c) => [c.id, c]));
const linesOf = (id: string) => CASES.get(id)!.lines;
const config = { service: 'write-model', environment: 'development' as const, region: 'region-1' };
// TypeScript keeps its released counter names; the shared names map onto them.
const COUNTER_NAMES: Record<string, string> = {
    written: 'written',
    invalid: 'invalid',
    queue_full: 'backpressure',
    io_errors: 'io',
    closed: 'closed',
    pending: 'pending',
};

/** Accepts one write, then reports back-pressure and never acknowledges until released. */
class Gate extends Writable {
    readonly lines: string[] = [];
    private open = false;
    private held: (() => void)[] = [];
    constructor() {
        super({ highWaterMark: 1 });
    }
    override _write(chunk: Buffer, _encoding: BufferEncoding, cb: (error?: Error | null) => void) {
        const done = () => {
            this.lines.push(chunk.toString());
            cb();
        };
        if (this.open) done();
        else this.held.push(done);
    }
    release() {
        this.open = true;
        for (const done of this.held.splice(0)) done();
    }
}

/** Fails its first write (and emits 'error') but is not destroyed: it stays writable. */
class FailFirst extends EventEmitter {
    readonly lines: string[] = [];
    readonly destroyed = false;
    readonly writable = true;
    readonly writableNeedDrain = false;
    private failed = false;
    write(chunk: string, cb: (error?: Error | null) => void): boolean {
        if (!this.failed) {
            this.failed = true;
            process.nextTick(() => {
                cb(new Error('broken pipe'));
                this.emit('error', new Error('broken pipe'));
            });
        } else {
            this.lines.push(chunk);
            process.nextTick(() => cb());
        }
        return true;
    }
}

/** Acknowledges every write after 10 ms. */
class Slow extends Writable {
    readonly lines: string[] = [];
    override _write(chunk: Buffer, _encoding: BufferEncoding, cb: (error?: Error | null) => void) {
        setTimeout(() => {
            this.lines.push(chunk.toString());
            cb();
        }, 10);
    }
}

class Ok extends Writable {
    readonly lines: string[] = [];
    override _write(chunk: Buffer, _encoding: BufferEncoding, cb: (error?: Error | null) => void) {
        this.lines.push(chunk.toString());
        cb();
    }
}

const messages = (lines: string[]) =>
    lines.map((line) => (parseRecord(line) as Record<string, unknown>).message);

it('the constants and counters match the shared model', async () => {
    expect(QUEUE_CAPACITY).toBe(MODEL.queue_capacity);
    expect(CLOSE_TIMEOUT_MS).toBe(MODEL.close_timeout_ms);
    const logger = createLogger(config, new Ok());
    expect(Object.keys(logger.stats()).sort()).toEqual(
        MODEL.counters.map((name) => COUNTER_NAMES[name]).sort(),
    );
    await logger.close();
});

it('blocked_output_never_blocks_caller', async () => {
    const stream = new Gate();
    const logger = createLogger(config, stream);
    const total = linesOf('blocked_output_never_blocks_caller');
    let slowest = 0;
    for (let i = 0; i < total; i++) {
        const start = performance.now();
        logger.log(`line ${i}`);
        slowest = Math.max(slowest, performance.now() - start);
    }
    expect(slowest).toBeLessThan(MODEL.caller_budget_ms);
    const dropped = logger.stats().backpressure;
    expect(dropped).toBeGreaterThanOrEqual(total - MODEL.queue_capacity - 1);
    expect(logger.stats().pending).toBe(total - dropped);
    stream.release(); // the output recovers: the queued lines are written
    expect(await logger.close()).toBe(true);
    expect(logger.stats()).toMatchObject({ written: total - dropped, pending: 0, io: 0 });
    expect(messages(stream.lines)).toEqual(
        Array.from({ length: total - dropped }, (_, i) => `line ${i}`),
    );
});

it('write_error_recovers', async () => {
    const stream = new FailFirst();
    const logger = createLogger(config, stream as unknown as Writable);
    for (let i = 0; i < linesOf('write_error_recovers'); i++)
        expect(logger.log(`line ${i}`)).toBe(true);
    expect(await logger.flush()).toBe(true);
    await nextTurn(); // after the 'error' event, the stream is still writable
    expect(logger.log('line 3')).toBe(true);
    expect(await logger.close()).toBe(true);
    expect(logger.stats()).toMatchObject({ io: 1, written: 3, pending: 0 });
    expect(messages(stream.lines)).toEqual(['line 1', 'line 2', 'line 3']);
});

it('close_drains', async () => {
    const stream = new Slow();
    const logger = createLogger(config, stream);
    const total = linesOf('close_drains');
    for (let i = 0; i < total; i++) logger.log(`line ${i}`);
    expect(await logger.close()).toBe(true);
    expect(logger.stats()).toMatchObject({ written: total, pending: 0 });
    expect(stream.lines).toHaveLength(total);
});

it('close_deadline', async () => {
    const stream = new Gate();
    const logger = createLogger(config, stream);
    const total = linesOf('close_deadline');
    for (let i = 0; i < total; i++) logger.log(`line ${i}`);
    const start = performance.now();
    expect(await logger.close()).toBe(false);
    const elapsed = performance.now() - start;
    expect(elapsed).toBeGreaterThanOrEqual(MODEL.close_timeout_ms - 50);
    expect(elapsed).toBeLessThan(MODEL.close_timeout_ms + 500);
    expect(logger.stats()).toMatchObject({ pending: total, written: 0 }); // undelivered lines stay counted
    stream.release();
    await new Promise((done) => setTimeout(done, 20));
    expect(logger.stats()).toMatchObject({ pending: 0, written: total });
}, 10_000);

it('log_after_close', async () => {
    const stream = new Ok();
    const logger = createLogger(config, stream);
    expect(await logger.close()).toBe(true);
    for (let i = 0; i < linesOf('log_after_close'); i++) expect(logger.log('too late')).toBe(false);
    expect(logger.stats()).toMatchObject({ closed: 1, written: 0 });
    expect(stream.lines).toEqual([]);
    expect(await logger.close()).toBe(true); // a second close is harmless
});

it('a destroyed stream: queued lines and later lines are counted as io', async () => {
    const stream = new Gate();
    const logger = createLogger(config, stream);
    for (let i = 0; i < 5; i++) logger.log(`line ${i}`);
    stream.destroy();
    await nextTurn();
    expect(logger.log('after destroy')).toBe(false);
    expect(logger.stats()).toMatchObject({ io: 6, pending: 0, written: 0 });
    await logger.close(0);
});

it('stdout_closed_lines_count_as_io', async () => {
    // process.stdout after EPIPE emits 'close' but keeps destroyed === false, writable === true.
    const stream = Object.assign(new EventEmitter(), {
        destroyed: false,
        writable: true,
        writableNeedDrain: false,
        write: () => true, // never calls back, like a dead pipe
    });
    const logger = createLogger(config, stream as unknown as Writable);
    stream.emit('close');
    for (let i = 0; i < 5; i++) expect(logger.log(`line ${i}`)).toBe(false);
    expect(logger.stats()).toMatchObject({ io: 5, pending: 0, written: 0, backpressure: 0 });
    const start = performance.now();
    expect(await logger.close()).toBe(true);
    expect(performance.now() - start).toBeLessThan(100);
});

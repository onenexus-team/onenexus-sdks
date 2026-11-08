import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Writable } from 'node:stream';
import { describe, expect, it } from 'vitest';
import {
    createLogger,
    parseRecord,
    validateRecord,
    type LogConfig,
    type LogFields,
    type LogOptions,
} from '@onenexus-team/observability';

interface Bound {
    max_bytes: number;
    prefix: string;
    suffix: string;
}
interface Case {
    id: string;
    level: NonNullable<LogOptions['level']>;
    message: unknown;
    fields: Record<string, unknown>;
    error?: { message: string; nested_calls: number };
    expect: {
        truncated: true | null;
        dropped_field_count: number | null;
        message?: unknown;
        message_max_bytes?: number;
        message_prefix?: string;
        message_suffix?: string;
        fields?: Record<string, unknown>;
        absent?: string[];
        field_bounds?: Record<string, Bound>;
        record_max_bytes?: number;
        error_type?: boolean;
        stacktrace_line_pattern?: string;
        stacktrace_max_bytes?: number;
        stacktrace_excludes?: string[];
    };
}
const suite = JSON.parse(
    readFileSync(
        process.env.ONENEXUS_LOGGING_SCENARIOS ?? resolve('../../../tests/logging/scenarios.json'),
        'utf8',
    ),
) as {
    degradation_cases: Case[];
    degradation_allowed_fields: string[];
    degradation_error_type: Record<string, string>;
};

const bytes = (text: unknown) => Buffer.byteLength(text as string);
function expand(value: unknown): unknown {
    if (typeof value !== 'object' || value === null) return value;
    const entries = Object.entries(value);
    if (entries.length === 2 && 'repeat' in value && 'count' in value)
        return (value.repeat as string).repeat(value.count as number);
    return Object.fromEntries(entries.map(([k, v]) => [k, expand(v)]));
}
function raiseNested(message: string, depth: number): never {
    if (depth > 1) raiseNested(message, depth - 1);
    throw new TypeError(message);
}
function capture(fn: () => void, frames = Error.stackTraceLimit): unknown {
    const limit = Error.stackTraceLimit;
    Error.stackTraceLimit = frames;
    try {
        fn();
    } catch (error) {
        return error;
    } finally {
        Error.stackTraceLimit = limit;
    }
    throw Error('expected_throw');
}
function sink(config: LogConfig) {
    const lines: string[] = [];
    const stream = new Writable({
        write(chunk: Buffer, _encoding, cb) {
            lines.push(chunk.toString());
            cb();
        },
    });
    return { lines, logger: createLogger(config, stream) };
}
const shared: LogConfig = {
    service: 'shared-test',
    environment: 'development',
    region: 'region-1',
    allowedFields: suite.degradation_allowed_fields,
};

describe('shared degradation: the line still arrives', () => {
    for (const c of suite.degradation_cases) {
        it(c.id, async () => {
            const { lines, logger } = sink(shared);
            const options: LogOptions = {
                level: c.level,
                fields: expand(c.fields) as LogFields,
            };
            if (c.error) {
                const { message, nested_calls } = c.error;
                options.error = capture(() => raiseNested(message, nested_calls));
            }
            expect(logger.log(expand(c.message) as string, options)).toBe(true);
            await logger.close();
            expect(logger.stats().invalid).toBe(0);
            expect(lines).toHaveLength(1);
            const line = lines[0]!.trimEnd();
            const row = parseRecord(line) as Record<string, unknown>;
            expect(validateRecord(row)).toEqual([]);
            const e = c.expect;
            expect(row['logging.truncated'] ?? null).toBe(e.truncated);
            expect(row['logging.dropped_field_count'] ?? null).toBe(e.dropped_field_count);
            if ('message' in e) expect(row.message).toBe(expand(e.message));
            else {
                expect(bytes(row.message)).toBeLessThanOrEqual(e.message_max_bytes!);
                expect(row.message).toMatch(new RegExp('^' + e.message_prefix!));
                expect((row.message as string).endsWith(e.message_suffix!)).toBe(true);
            }
            for (const [key, value] of Object.entries(
                expand(e.fields ?? {}) as Record<string, unknown>,
            ))
                expect(row[key]).toBe(value);
            for (const key of e.absent ?? []) expect(row).not.toHaveProperty([key]);
            for (const [key, bound] of Object.entries(e.field_bounds ?? {})) {
                const value = row[key] as string;
                expect(bytes(value)).toBeLessThanOrEqual(bound.max_bytes);
                expect(value.startsWith(bound.prefix) && value.endsWith(bound.suffix)).toBe(true);
            }
            if (e.record_max_bytes) expect(bytes(line)).toBeLessThanOrEqual(e.record_max_bytes);
            if (e.error_type) {
                expect(row['error.type']).toBe(suite.degradation_error_type.typescript);
                const stack = row['exception.stacktrace'] as string;
                expect(bytes(stack)).toBeLessThanOrEqual(e.stacktrace_max_bytes!);
                const pattern = new RegExp(e.stacktrace_line_pattern!);
                for (const frame of stack.split('\n')) expect(frame).toMatch(pattern);
                expect(stack.split('\n')[0]).toMatch(
                    /^at raiseNested \(degradation\.test\.ts:\d+\)$/,
                );
                expect(stack.split('\n')[1]).toMatch(/^at raiseNested \(/);
                for (const marker of e.stacktrace_excludes ?? [])
                    expect(line).not.toContain(marker);
            }
        });
    }
});

describe('degradation details', () => {
    const rowsOf = (lines: string[]) => lines.map((s) => parseRecord(s) as Record<string, unknown>);

    it('a caller-supplied error.type wins; the stack is still added', async () => {
        const { lines, logger } = sink({ ...shared, allowedFields: ['error.type'] });
        const error = capture(() => raiseNested('secret-detail', 1));
        logger.log('Lookup failed', { fields: { 'error.type': 'LookupFailed' }, error });
        await logger.close();
        const [row] = rowsOf(lines);
        expect(row!['error.type']).toBe('LookupFailed');
        expect(row!['exception.stacktrace']).toMatch(/^at raiseNested \(/);
        expect(lines[0]).not.toContain('secret-detail');
    });

    it('a non-Error error value is ignored silently', async () => {
        const { lines, logger } = sink(shared);
        for (const error of ['secret-detail', 42, null, { message: 'secret-detail' }])
            expect(logger.log('Failed', { error })).toBe(true);
        await logger.close();
        for (const row of rowsOf(lines)) {
            expect(row).not.toHaveProperty(['error.type']);
            expect(row).not.toHaveProperty(['exception.stacktrace']);
            expect(row).not.toHaveProperty(['logging.dropped_field_count']);
        }
        expect(lines.join('')).not.toContain('secret-detail');
    });

    it('an Error with an unusable name falls back to its constructor; deep stacks fit 2,048 bytes', async () => {
        class LookupError extends Error {}
        const error = new LookupError('secret-detail');
        error.name = 'not a type';
        const { lines, logger } = sink(shared);
        logger.log('Failed', { error });
        const deep = capture(() => raiseNested('x', 400), 200);
        logger.log('Failed', { error: deep });
        await logger.close();
        const [first, second] = rowsOf(lines);
        expect(first!['error.type']).toBe('LookupError');
        const stack = second!['exception.stacktrace'] as string;
        expect(bytes(stack)).toBeLessThanOrEqual(2048);
        expect(second!['logging.truncated']).toBe(true);
        expect(stack.split('\n').length).toBeLessThan(200);
        expect(stack.split('\n').every((f) => f.startsWith('at raiseNested ('))).toBe(true);
    });

    it('32 allowed fields plus unknown ones: the unknown ones are removed and counted', async () => {
        const names = Array.from({ length: 32 }, (_, i) => `f${i}`);
        const { lines, logger } = sink({ ...shared, allowedFields: names });
        const fields = Object.fromEntries(
            [...names, 'f32', 'f33', 'f34'].map((k, i) => [k, i]),
        ) as LogFields;
        expect(logger.log('Many fields', { fields })).toBe(true);
        await logger.close();
        const [row] = rowsOf(lines);
        expect(row!['logging.dropped_field_count']).toBe(3);
        for (const name of names) expect(row).toHaveProperty([name]);
        expect(validateRecord(row)).toEqual([]);
    });

    it('an allowed key after 40 unknown keys is kept', async () => {
        const { lines, logger } = sink(shared);
        const fields = Object.fromEntries([
            ...Array.from({ length: 40 }, (_, i) => [`unknown${i}`, i]),
            ['shared.note', 'kept'],
        ]) as LogFields;
        expect(logger.log('Many unknown fields', { fields })).toBe(true);
        await logger.close();
        const [row] = rowsOf(lines);
        expect(row).toMatchObject({ 'shared.note': 'kept', 'logging.dropped_field_count': 40 });
    });

    it('a malformed-Unicode string field is removed and counted, not the record', async () => {
        const { lines, logger } = sink(shared);
        expect(
            logger.log('Bad text', { fields: { 'shared.note': 'x\ud800', 'shared.a': 'ok' } }),
        ).toBe(true);
        await logger.close();
        const [row] = rowsOf(lines);
        expect(row).not.toHaveProperty(['shared.note']);
        expect(row).toMatchObject({ 'shared.a': 'ok', 'logging.dropped_field_count': 1 });
        expect(logger.stats().invalid).toBe(0);
    });

    it('a message changed after the stack was formatted yields no frames', async () => {
        const error = new Error('lookup\n    at token-s3cr3t (db.js:1:1)');
        void error.stack; // V8 formats the header now, with the original message.
        error.message = 'redacted';
        const { lines, logger } = sink(shared);
        logger.log('Failed', { error });
        await logger.close();
        const [row] = rowsOf(lines);
        expect(row!['error.type']).toBe('Error');
        expect(row).not.toHaveProperty(['exception.stacktrace']);
        expect(lines.join('')).not.toContain('token-s3cr3t');
    });

    it('constructor and aliased frames become one token', async () => {
        class Widget {
            constructor() {
                raiseNested('x', 1);
            }
        }
        const error = capture(() => new Widget());
        // Insert one frame right after the header line.
        const stack = (error as Error).stack!;
        const header = stack.indexOf('\n');
        (error as Error).stack =
            stack.slice(0, header) +
            '\n    at Foo.bar [as baz] (file:///srv/app/x.ts?v=1:3:4)' +
            stack.slice(header);
        const { lines, logger } = sink(shared);
        logger.log('Failed', { error });
        await logger.close();
        const frames = (rowsOf(lines)[0]!['exception.stacktrace'] as string).split('\n');
        expect(frames[0]).toBe('at Foo.bar (x.ts:3)');
        expect(frames[2]).toMatch(/^at Widget \(degradation\.test\.ts:\d+\)$/);
        const pattern = new RegExp(
            suite.degradation_cases.find((c) => c.error)!.expect.stacktrace_line_pattern!,
        );
        for (const frame of frames) expect(frame).toMatch(pattern);
    });

    it('a caller stack wins without a truncation flag from the SDK stack', async () => {
        const { lines, logger } = sink(shared);
        const error = capture(() => raiseNested('x', 400), 200);
        logger.log('Failed', {
            fields: { 'exception.stacktrace': 'at caller (app.src:1)' },
            error,
        });
        await logger.close();
        const [row] = rowsOf(lines);
        expect(row!['exception.stacktrace']).toBe('at caller (app.src:1)');
        expect(row!['error.type']).toBe('TypeError');
        expect(row).not.toHaveProperty(['logging.truncated']);
    });

    it('clamps logging.dropped_field_count at 64', async () => {
        const { lines, logger } = sink(shared);
        const fields = Object.fromEntries(
            Array.from({ length: 100 }, (_, i) => [`unknown${i}`, i]),
        ) as LogFields;
        expect(logger.log('Many unknown fields', { fields })).toBe(true);
        await logger.close();
        const [row] = rowsOf(lines);
        expect(row!['logging.dropped_field_count']).toBe(64);
        expect(validateRecord(row)).toEqual([]);
    });

    it('never splits a surrogate pair', async () => {
        const { lines, logger } = sink(shared);
        // 1,021 budget bytes: 'a' + 255 four-byte emoji = 1,021, the next pair does not fit.
        logger.log('a' + '😀'.repeat(400), { fields: { 'shared.note': 'ab' + '😀'.repeat(400) } });
        await logger.close();
        const [row] = rowsOf(lines);
        const message = row!.message as string;
        const note = row!['shared.note'] as string;
        for (const value of [message, note]) {
            expect(value.isWellFormed()).toBe(true);
            expect(value.endsWith('…')).toBe(true);
            expect(bytes(value)).toBeLessThanOrEqual(1024);
        }
        expect(message).toBe('a' + '😀'.repeat(255) + '…');
        expect(note).toBe('ab' + '😀'.repeat(254) + '…');
        expect(row!['logging.truncated']).toBe(true);
    });

    it('oversize records shorten the stack before removing fields; request-field keys stay', async () => {
        const { lines, logger } = sink({ ...shared, allowedFields: ['a', 'b', 'c'] });
        const error = capture(() => raiseNested('x', 400), 200);
        logger.log('m'.repeat(900), {
            fields: { a: 'x'.repeat(900), b: 'y'.repeat(900) },
            error,
        });
        logger.log('m'.repeat(1000), {
            fields: {
                a: 'x'.repeat(1000),
                b: 'y'.repeat(1000),
                c: 'w'.repeat(1000),
                'http.route': '/' + 'z'.repeat(199),
            },
            error,
        });
        await logger.close();
        const [first, second] = rowsOf(lines);
        expect(first).toMatchObject({ a: 'x'.repeat(900), b: 'y'.repeat(900) });
        expect(first).not.toHaveProperty(['logging.dropped_field_count']);
        expect(first!['logging.truncated']).toBe(true);
        expect(first!['exception.stacktrace']).toMatch(/^at raiseNested/);
        // Stack gone, then a tie between a, b and c: key name descending removes c first.
        expect(second).not.toHaveProperty(['exception.stacktrace']);
        expect(second).not.toHaveProperty(['c']);
        expect(second).toMatchObject({
            a: 'x'.repeat(1000),
            b: 'y'.repeat(1000),
            'http.route': '/' + 'z'.repeat(199),
            'logging.dropped_field_count': 1,
        });
        expect(second!['error.type']).toBe('TypeError');
        for (const line of lines) expect(bytes(line.trimEnd())).toBeLessThanOrEqual(4096);
    });
});

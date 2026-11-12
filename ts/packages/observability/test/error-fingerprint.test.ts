// Error fingerprint (tests/logging/scenarios.json `error_fingerprint`, design review F1).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Writable } from 'node:stream';
import { describe, expect, it } from 'vitest';
import {
    createLogger,
    errorFingerprint,
    parseRecord,
    validateRecord,
    type LogConfig,
    type LogOptions,
} from '@onenexus-team/observability';

type Case = { id: string; error_type: string; stacktrace: string | null; fingerprint: string };
const SPEC = (
    JSON.parse(
        readFileSync(
            process.env.ONENEXUS_LOGGING_SCENARIOS ??
                resolve('../../../tests/logging/scenarios.json'),
            'utf8',
        ),
    ) as { error_fingerprint: { field: string; cases: Case[] } }
).error_fingerprint;
const FIELD = SPEC.field;
const CONFIG: LogConfig = {
    service: 'fingerprint-test',
    environment: 'development',
    region: 'region-1',
    // The shared degradation allowlist: a caller may supply the stack.
    allowedFields: ['shared.note', 'exception.stacktrace'],
};

async function emit(...calls: [string, LogOptions][]): Promise<Record<string, unknown>[]> {
    const lines: string[] = [];
    const stream = new Writable({
        write(chunk: Buffer, _encoding, cb) {
            lines.push(chunk.toString());
            cb();
        },
    });
    const logger = createLogger(CONFIG, stream);
    for (const [message, options] of calls) expect(logger.log(message, options)).toBe(true);
    await logger.close();
    expect(logger.stats().invalid).toBe(0);
    return lines.map((line) => parseRecord(line.trimEnd()) as Record<string, unknown>);
}

function failure(): Error {
    return new TypeError('private-sentinel');
}

describe('vectors', () => {
    // type_only, frames, line_numbers_ignored, frame_without_file,
    // type_changes_fingerprint, multibyte
    for (const c of SPEC.cases)
        it(c.id, () => expect(errorFingerprint(c.error_type, c.stacktrace)).toBe(c.fingerprint));
});

it('logged_error_has_fingerprint', async () => {
    const [row] = await emit(['Job failed', { level: 'ERROR', error: failure() }]);
    expect(row![FIELD]).toBe(
        errorFingerprint(row!['error.type'] as string, row!['exception.stacktrace'] as string),
    );
    const text = JSON.stringify(row, (_k, v: unknown) => (typeof v === 'bigint' ? `${v}` : v));
    expect(text).not.toContain('private-sentinel');
    expect(validateRecord(row!)).toEqual([]);
});

it('same_error_same_fingerprint', async () => {
    const rows = await emit(
        ...[0, 1].map((): [string, LogOptions] => ['Job failed', { level: 'ERROR', error: failure() }]),
    );
    expect(rows[0]![FIELD]).toBe(rows[1]![FIELD]);
});

it('stable_when_fitted', async () => {
    const stack = Array.from({ length: 55 }, (_, i) => `at function_${i} (deep_module.py:${i})`).join(
        '\n',
    );
    expect(Buffer.byteLength(stack)).toBeLessThan(2048); // whole: only fitting can shorten it
    const [row] = await emit([
        'x'.repeat(1000),
        {
            level: 'ERROR',
            error: failure(),
            fields: { 'exception.stacktrace': stack, 'shared.note': 'n'.repeat(1000) },
        },
    ]);
    expect(row!['exception.stacktrace']).not.toBe(stack); // the record was fitted
    expect(row!['logging.truncated']).toBe(true);
    expect(row![FIELD]).toBe(errorFingerprint(row!['error.type'] as string, stack));
});

it('caller_value_removed', async () => {
    const [row] = await emit([
        'Job failed',
        { level: 'ERROR', error: failure(), fields: { [FIELD]: '0000000000000000' } },
    ]);
    expect(row![FIELD]).not.toBe('0000000000000000');
    expect(row!['logging.dropped_field_count']).toBe(1);
});

it('no_error_no_fingerprint', async () => {
    const [row] = await emit(['Job done', {}]);
    expect(row).not.toHaveProperty([FIELD]);
});

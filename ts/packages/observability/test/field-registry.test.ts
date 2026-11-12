// One field registry (tests/logging/scenarios.json `field_registry`, design review E1): allowed
// custom field names are checked when a logger is configured; values are flat scalars of their
// registered type. Each shared case runs as one test named by its case id.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Writable } from 'node:stream';
import { describe, expect, it } from 'vitest';
import {
    MAX_CUSTOM_FIELDS,
    checkAllowedFields,
    createLogger,
    parseRecord,
    validateRecord,
    type LogConfig,
    type LogFields,
} from '@onenexus-team/observability';

type Names = string[] | { prefix: string; count: number; repeat?: string };
interface ConfigCase {
    id: string;
    names: Names;
    accepted: boolean;
    reason?: string;
}
interface ValueCase {
    id: string;
    fields: Record<string, unknown>;
    kept: string[];
    dropped_field_count: number | null;
}
const spec = (
    JSON.parse(
        readFileSync(
            process.env.ONENEXUS_LOGGING_SCENARIOS ??
                resolve('../../../tests/logging/scenarios.json'),
            'utf8',
        ),
    ) as {
        field_registry: {
            config_error: string;
            config_cases: ConfigCase[];
            value_cases: ValueCase[];
            value_allowed_fields: string[];
        };
    }
).field_registry;

// Listed verbatim: tests/logging checks that every shared case id appears in this file.
const CONFIG_CASE_IDS = [
    'accepts_service_namespace',
    'accepts_registered_field',
    'accepts_otel_namespace',
    'accepts_registered_in_reserved',
    'accepts_max_custom_fields',
    'rejects_protected',
    'rejects_bad_format',
    'rejects_too_many_segments',
    'rejects_too_long',
    'rejects_reserved_namespace',
    'rejects_unregistered_flat',
    'rejects_unregistered_namespace',
    'rejects_too_many',
];
const VALUE_CASE_IDS = [
    'scalar_values_kept',
    'object_value_removed',
    'array_value_removed',
    'registered_type_enforced',
    'registered_type_accepted',
];
const byId = <T extends { id: string }>(cases: T[], id: string): T =>
    cases.find((c) => c.id === id)!;

/** scenarios.json `names_expansion`. */
function expandNames(names: Names): string[] {
    if (Array.isArray(names)) return names;
    if (names.repeat !== undefined) return [names.prefix + names.repeat.repeat(names.count)];
    return Array.from({ length: names.count }, (_, i) => names.prefix + String(i));
}
/** The configuration error for a rejected case: `<code>: <rule>: <detail>`. */
function expectedError(c: ConfigCase, names: string[]): string {
    const detail = c.reason === 'too_many' ? `${names.length} > ${MAX_CUSTOM_FIELDS}` : names[0];
    return `${spec.config_error}: ${c.reason}: ${detail}`;
}
const config = (allowedFields: readonly string[]): LogConfig => ({
    service: 'field-registry-test',
    environment: 'development',
    region: 'region-1',
    allowedFields,
});
function sink(allowedFields: readonly string[]) {
    const lines: string[] = [];
    const stream = new Writable({
        write(chunk: Buffer, _encoding, cb) {
            lines.push(chunk.toString());
            cb();
        },
    });
    return { lines, logger: createLogger(config(allowedFields), stream) };
}

it('every shared field_registry case is listed here', () => {
    expect(spec.config_cases.map((c) => c.id)).toEqual(CONFIG_CASE_IDS);
    expect(spec.value_cases.map((c) => c.id)).toEqual(VALUE_CASE_IDS);
});

describe('shared field registry: allowed names at configuration', () => {
    for (const id of CONFIG_CASE_IDS) {
        it(id, () => {
            const c = byId(spec.config_cases, id);
            const names = expandNames(c.names);
            if (c.accepted) {
                expect(() => checkAllowedFields(names)).not.toThrow();
                expect(() => createLogger(config(names), new Writable())).not.toThrow();
            } else {
                const error = new Error(expectedError(c, names));
                expect(() => checkAllowedFields(names)).toThrow(error);
                expect(() => createLogger(config(names), new Writable())).toThrow(error);
            }
        });
    }
});

describe('shared field registry: values at log time', () => {
    for (const id of VALUE_CASE_IDS) {
        it(id, async () => {
            const c = byId(spec.value_cases, id);
            const { lines, logger } = sink(spec.value_allowed_fields);
            expect(logger.log('Fields', { fields: c.fields as LogFields })).toBe(true);
            await logger.close();
            expect(lines).toHaveLength(1);
            const row = parseRecord(lines[0]!) as Record<string, unknown>;
            expect(validateRecord(row)).toEqual([]);
            const kept = Object.keys(c.fields).filter((name) => name in row);
            expect(kept.sort()).toEqual(c.kept);
            for (const name of kept) expect(row[name]).toEqual(c.fields[name]);
            expect(row['logging.dropped_field_count'] ?? null).toBe(c.dropped_field_count);
        });
    }
});

describe('field registry details', () => {
    it('the cap is the schema max_custom_fields, the largest accepted case', () => {
        const largest = byId(spec.config_cases, 'accepts_max_custom_fields');
        expect(expandNames(largest.names)).toHaveLength(MAX_CUSTOM_FIELDS);
    });

    it('prototype keys are not registered fields or namespaces', () => {
        for (const name of ['constructor', 'tostring', 'constructor.x'])
            expect(() => checkAllowedFields([name])).toThrow(
                new Error(`${spec.config_error}: namespace: ${name}`),
            );
    });

    it('a non-string name or a non-array list is a configuration error', () => {
        expect(() => checkAllowedFields([42] as unknown as string[])).toThrow(
            new Error(`${spec.config_error}: format: number`),
        );
        expect(() => checkAllowedFields('job.id' as unknown as string[])).toThrow(
            new Error(`${spec.config_error}: not an array`),
        );
    });

    it('the first failing name is reported', () => {
        expect(() => checkAllowedFields(['job.id', 'msg', 'message'])).toThrow(
            new Error(`${spec.config_error}: namespace: msg`),
        );
    });

    it('a non-finite number is removed and counted, also for a number field', async () => {
        const { lines, logger } = sink(['example.f', 'duration_ms']);
        logger.log('Fields', { fields: { 'example.f': Infinity, duration_ms: NaN } });
        await logger.close();
        const row = parseRecord(lines[0]!) as Record<string, unknown>;
        expect(row).not.toHaveProperty(['example.f']);
        expect(row).not.toHaveProperty(['duration_ms']);
        expect(row['logging.dropped_field_count']).toBe(2);
    });
});

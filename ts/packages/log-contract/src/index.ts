import { Ajv2020 } from 'ajv/dist/2020.js';
import { manifestText, schemaText, vectorsText } from './generated/data.js';

interface Manifest {
    version: string;
    sha256: string;
    record_cases: number;
    context_cases: number;
}
interface Definition {
    required: string[];
    properties: Record<string, Record<string, unknown>>;
}
interface Schema {
    $defs: Record<string, Definition> & { common: Definition };
    'x-semantic-checks': { message_max_utf8_bytes: number; record_max_compact_utf8_bytes: number };
}
interface Vectors {
    record_cases: { id: string; profile: string; record: unknown; errors: string[] }[];
    context_cases: { id: string; trusted: boolean; traceparent: string; preserve_trace: boolean }[];
}
const manifest = JSON.parse(manifestText) as Manifest;
const schema = JSON.parse(schemaText) as Schema;
const ajv = new Ajv2020({ allErrors: true, strict: true });
const validators = new Map(
    Object.entries(schema.$defs).map(([name, definition]) => [
        name,
        ajv.compile(definition as object),
    ]),
);
export const CONTRACT_VERSION: string = manifest.version;
export const CONTRACT_DIGEST: string = manifest.sha256;
export const MAX_MESSAGE_BYTES: number = schema['x-semantic-checks'].message_max_utf8_bytes;
export const MAX_RECORD_BYTES: number = schema['x-semantic-checks'].record_max_compact_utf8_bytes;
export const COMMON_FIELDS: readonly string[] = Object.freeze(
    Object.keys(schema.$defs.common.properties),
);

/** Parse integer timestamps without rounding int64 values through a JS number. */
export function parseRecord(text: string): unknown {
    return JSON.parse(text, (key: string, value: unknown, context?: { source?: string }) => {
        if (
            key === 'timestamp' &&
            typeof value === 'number' &&
            context?.source &&
            /^-?\d+$/.test(context.source)
        ) {
            return BigInt(context.source);
        }
        return value;
    });
}

/** Fresh copies: consumers cannot mutate the validator's schema or shared cases. */
export function loadContract(): { manifest: Manifest; schema: Schema; vectors: Vectors } {
    return {
        manifest: JSON.parse(manifestText) as Manifest,
        schema: JSON.parse(schemaText) as Schema,
        vectors: parseRecord(vectorsText) as Vectors,
    };
}

const exactSchema = JSON.parse(
    schemaText,
    (key: string, value: unknown, context?: { source?: string }) =>
        ['minimum', 'maximum'].includes(key) && typeof value === 'number' && context?.source
            ? BigInt(context.source)
            : value,
) as Schema;
const timestampBounds = exactSchema.$defs.common.properties.timestamp as {
    minimum: bigint;
    maximum: bigint;
};

const code = (field: string) =>
    field === 'message'
        ? 'missing_or_invalid_message'
        : field === 'trace_id'
          ? 'missing_or_invalid_trace_id'
          : 'schema_invalid';

// Reject coercions, getters, toJSON hooks, non-finite numbers and malformed Unicode.
// This is not an arbitrary-object serializer; callers supply plain JSON data.
function jsonValue(value: unknown, depth = 0): string {
    if (depth > 32) throw Error('invalid_json_record');
    if (value === null || typeof value === 'boolean') return String(value);
    if (typeof value === 'string') {
        if (!value.isWellFormed()) throw Error('invalid_json_record');
        return JSON.stringify(value);
    }
    if (typeof value === 'number' && Number.isFinite(value)) return JSON.stringify(value);
    if (typeof value !== 'object' || value === null) throw Error('invalid_json_record');
    if (Array.isArray(value))
        return '[' + Array.from(value as unknown[], (v) => jsonValue(v, depth + 1)).join(',') + ']';
    const prototype: unknown = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw Error('invalid_json_record');
    const entries = Object.getOwnPropertyDescriptors(value);
    return (
        '{' +
        Object.entries(entries)
            .filter(([, d]) => d.enumerable)
            .map(([k, d]) => {
                if (!('value' in d)) throw Error('invalid_json_record');
                const item: unknown = d.value;
                const encoded =
                    depth === 0 && k === 'timestamp' && typeof item === 'bigint'
                        ? item.toString()
                        : jsonValue(item, depth + 1);
                return jsonValue(k) + ':' + encoded;
            })
            .join(',') +
        '}'
    );
}

export function validateRecord(record: unknown, profile = 'common'): string[] {
    const validate = validators.get(profile);
    if (!validate) return ['unknown_profile'];
    if (typeof record !== 'object' || record === null || Array.isArray(record))
        return ['schema_invalid'];
    const errors = new Set<string>();
    try {
        const encoded = jsonValue(record);
        const normalized = JSON.parse(encoded) as Record<string, unknown>;
        const exact = parseRecord(encoded) as Record<string, unknown>;
        const timestamp = exact.timestamp;
        // AJV handles the remaining schema. Check int64 exactly, before JS rounding.
        if (
            typeof timestamp !== 'bigint' ||
            timestamp < timestampBounds.minimum ||
            timestamp > timestampBounds.maximum
        )
            errors.add('schema_invalid');
        if (typeof timestamp === 'bigint') normalized.timestamp = 0;
        validate(normalized);
        for (const error of validate.errors ?? []) {
            const field: unknown =
                error.keyword === 'required'
                    ? error.params.missingProperty
                    : error.instancePath.split('/')[1];
            errors.add(code(typeof field === 'string' ? field : ''));
        }
        if (
            typeof normalized.message === 'string' &&
            Buffer.byteLength(normalized.message) > MAX_MESSAGE_BYTES
        )
            errors.add('missing_or_invalid_message');
        if (Buffer.byteLength(encoded) > MAX_RECORD_BYTES) errors.add('record_too_large');
    } catch {
        errors.add('invalid_json_record');
    }
    return [...errors].sort();
}

export class ContractViolation extends Error {
    constructor(public readonly codes: readonly string[]) {
        super(codes.join(','));
        this.name = 'ContractViolation';
    }
}

export function encodeRecord(record: unknown, profile = 'common'): string {
    const errors = validateRecord(record, profile);
    if (errors.length) throw new ContractViolation(errors);
    return jsonValue(record);
}

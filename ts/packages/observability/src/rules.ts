import { Ajv2020 } from 'ajv/dist/2020.js';
import schemaData from './schema.json';
const schemaText = JSON.stringify(schemaData);


interface Definition {
    required: string[];
    properties: Record<string, Record<string, unknown>>;
}
interface Schema {
    $schema: string;
    $defs: Record<string, object> & { common: Definition };
    'x-protected-fields': string[];
    'x-semantic-checks': {
        message_max_utf8_bytes: number;
        record_max_compact_utf8_bytes: number;
        field_max_utf8_bytes: number;
        stacktrace_max_utf8_bytes: number;
    };
    'x-field-registry': {
        name_pattern: string;
        name_max_chars: number;
        max_custom_fields: number;
        namespaces: Record<string, string>;
        reserved_namespaces: Record<string, string>;
        fields: Record<string, { type: string }>;
    };
}
const schema = JSON.parse(schemaText) as Schema;
const ajv = new Ajv2020({ allErrors: true, strict: true });
const validators = new Map(
    Object.keys(schema.$defs).map((name) => [
        name,
        ajv.compile({ $schema: schema.$schema, $defs: schema.$defs, $ref: `#/$defs/${name}` }),
    ]),
);
export const CONTRACT_VERSION = "0.5.0"; // Log-format identity, not the SDK version.
// sha256 of the bundled schema.json; equal in every language (tests/logging).
export const CONTRACT_DIGEST = "cf62150214247ebcfe4fcc0c3dd69f1c6d9c15d2d634f156fe3406f0b9feb4a1";
export const MAX_MESSAGE_BYTES: number = schema['x-semantic-checks'].message_max_utf8_bytes;
export const MAX_RECORD_BYTES: number = schema['x-semantic-checks'].record_max_compact_utf8_bytes;
export const MAX_FIELD_BYTES: number = schema['x-semantic-checks'].field_max_utf8_bytes;
export const MAX_STACKTRACE_BYTES: number = schema['x-semantic-checks'].stacktrace_max_utf8_bytes;
export const MAX_DROPPED_FIELD_COUNT = schema.$defs.common.properties['logging.dropped_field_count']
    ?.maximum as number;

// The field registry (design review E1): every set and limit comes from schema.json.
const registry = schema['x-field-registry'];
// Logger-owned fields stay protected when optional shared fields are added.
const PROTECTED = new Set(schema['x-protected-fields']);
const NAME_PATTERN = new RegExp(registry.name_pattern);
const NAMESPACES = new Set(Object.keys(registry.namespaces));
const RESERVED_NAMESPACES = new Set(Object.keys(registry.reserved_namespaces));
/** One predicate per schema `value_types` entry. */
const VALUE_TYPES = {
    string: (value: unknown) => typeof value === 'string',
    integer: (value: unknown) => Number.isInteger(value),
    number: (value: unknown) => typeof value === 'number' && Number.isFinite(value),
    boolean: (value: unknown) => typeof value === 'boolean',
    null: (value: unknown) => value === null,
} as const;
const isScalar = (value: unknown) => Object.values(VALUE_TYPES).some((accepts) => accepts(value));
// A Map, not an object: a name such as `constructor` must not match a prototype key.
const REGISTERED = new Map(
    Object.entries(registry.fields).map(([name, { type }]) => {
        if (!Object.hasOwn(VALUE_TYPES, type)) throw Error(`unknown_value_type: ${type}`);
        return [name, VALUE_TYPES[type as keyof typeof VALUE_TYPES]];
    }),
);
/** Most custom field names one logger may allow. */
export const MAX_CUSTOM_FIELDS: number = registry.max_custom_fields;

/** The first registry rule a name breaks, with its detail, or undefined when it may be logged. */
function registryFailure(name: unknown): string | undefined {
    // In check_order (tests/logging/scenarios.json `field_registry`).
    if (typeof name === 'string' && PROTECTED.has(name)) return `protected: ${name}`;
    if (
        typeof name !== 'string' ||
        name.length > registry.name_max_chars ||
        !NAME_PATTERN.test(name)
    )
        return `format: ${typeof name === 'string' ? name : typeof name}`;
    if (REGISTERED.has(name)) return undefined;
    const [head = '', ...rest] = name.split('.');
    if (RESERVED_NAMESPACES.has(head)) return `reserved: ${name}`;
    if (!rest.length || !NAMESPACES.has(head)) return `namespace: ${name}`;
    return undefined;
}

/**
 * Check a logger's allowed custom field names against the field registry; createLogger calls
 * it. Throws `invalid_allowed_fields: <rule>: <name>`.
 */
export function checkAllowedFields(names: readonly string[]): void {
    if (!Array.isArray(names)) throw new Error('invalid_allowed_fields: not an array');
    if (names.length > MAX_CUSTOM_FIELDS)
        throw new Error(`invalid_allowed_fields: too_many: ${names.length} > ${MAX_CUSTOM_FIELDS}`);
    for (const name of names as readonly unknown[]) {
        const failure = registryFailure(name);
        if (failure) throw new Error(`invalid_allowed_fields: ${failure}`);
    }
}

/** A custom field value is a flat scalar; a registered field's is of its type, or null. */
export function acceptsFieldValue(name: string, value: unknown): boolean {
    return value === null || (REGISTERED.get(name) ?? isScalar)(value);
}

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

const timestampBounds = { minimum: 0n, maximum: 9223372036854775807n };

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
    if (Array.isArray(value)) {
        const items: string[] = [];
        for (let index = 0; index < value.length; index++) {
            const descriptor = Object.getOwnPropertyDescriptor(value, index);
            if (!descriptor || !('value' in descriptor)) throw Error('invalid_json_record');
            items.push(jsonValue(descriptor.value as unknown, depth + 1));
        }
        return '[' + items.join(',') + ']';
    }
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

/** Compact UTF-8 size of plain JSON data; throws where encodeRecord would. */
export function encodedBytes(value: unknown): number {
    return Buffer.byteLength(jsonValue(value));
}

export function validateRecord(record: unknown, profile = 'common'): string[] {
    const validate = validators.get(profile);
    if (!validate) return ['unknown_profile'];
    if (typeof record !== 'object' || record === null || Array.isArray(record))
        return ['schema_invalid'];
    const errors = new Set<string>();
    try {
        const inputTimestamp: unknown = Object.getOwnPropertyDescriptor(record, 'timestamp')?.value;
        if (typeof inputTimestamp === 'number' && !Number.isSafeInteger(inputTimestamp))
            errors.add('schema_invalid');
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

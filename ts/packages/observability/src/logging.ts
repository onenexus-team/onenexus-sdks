import type { Writable } from 'node:stream';
import {
    COMMON_FIELDS,
    MAX_DROPPED_FIELD_COUNT,
    MAX_FIELD_BYTES,
    MAX_MESSAGE_BYTES,
    MAX_RECORD_BYTES,
    MAX_STACKTRACE_BYTES,
    ContractViolation,
    encodeRecord,
    encodedBytes,
    validateRecord,
} from './rules.js';
import { currentTraceId } from './context.js';
import { REQUEST_FIELDS, currentRequestFields } from './request.js';

export type LogFields = Readonly<Record<string, string | number | boolean | null>>;
export interface LogConfig {
    service: string;
    environment: 'development' | 'staging' | 'prod';
    region: string;
    allowedFields?: readonly string[];
}
export interface LogOptions {
    level?: 'TRACE' | 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'FATAL';
    event?: string;
    outcome?: string;
    fields?: LogFields;
    /** Adds error.type and exception.stacktrace (frames only, never the message). */
    error?: unknown;
}
export interface JsonLogger {
    /** true = submitted to stream; this is not proof of collector/Loki delivery. */
    log(message: string, options?: LogOptions): boolean;
    stats(): Readonly<{
        written: number;
        invalid: number;
        backpressure: number;
        io: number;
        closed: number;
        pending: number;
    }>;
    flush(timeoutMs?: number): Promise<boolean>;
    close(timeoutMs?: number): Promise<boolean>;
}

const ERROR_TYPE_FIELD = 'error.type';
const STACKTRACE_FIELD = 'exception.stacktrace';
const TRUNCATED_FIELD = 'logging.truncated';
const DROPPED_FIELD = 'logging.dropped_field_count';
const TRUNCATION_MARK = '\u2026';
const ERROR_TYPE_PATTERN = /^\S{1,128}$/;
// V8 frames: `at [async ]fn (path:line:col)` or `at [async ]path:line:col`.
const NAMED_FRAME = /^at (?:async )?(.+?) \(([^()]+):(\d+):\d+\)$/;
const ANONYMOUS_FRAME = /^at (?:async )?([^()]+):(\d+):\d+$/;

/** Cut at a code-point boundary so the text plus the mark fits `limit` UTF-8 bytes. */
function shorten(text: string, limit: number): [string, boolean] {
    if (Buffer.byteLength(text) <= limit) return [text, false];
    let budget = limit - Buffer.byteLength(TRUNCATION_MARK);
    let kept = '';
    for (const char of text) {
        budget -= Buffer.byteLength(char);
        if (budget < 0) break;
        kept += char;
    }
    return [kept + TRUNCATION_MARK, true];
}

/** Keep whole frames, innermost first, within the stack budget. */
function frames(lines: string[]): [string, boolean] {
    const kept: string[] = [];
    let size = 0;
    for (const raw of lines) {
        const [line, cut] = shorten(raw, MAX_STACKTRACE_BYTES);
        const cost = Buffer.byteLength(line) + (kept.length ? 1 : 0);
        if (cut || size + cost > MAX_STACKTRACE_BYTES)
            return [kept.length ? kept.join('\n') : line, true];
        kept.push(line);
        size += cost;
    }
    return [kept.join('\n'), false];
}

/** `new Foo` → `Foo`, `x [as y]` → `x`; other whitespace → `_` (one token per frame). */
function functionName(fn: string): string {
    return (
        fn
            .replace(/^(?:new |async )+/, '')
            .replace(/ \[as [^\]]*\]$/, '')
            .replace(/\s+/g, '_') || '<anonymous>'
    );
}

/** Type and frames of an Error; never its message. Non-errors yield nothing. */
function errorFields(error: unknown): [Record<string, string>, boolean] {
    try {
        if (typeof error !== 'object' || error === null) return [{}, false];
        const { name, stack, message } = error as Record<string, unknown>;
        if (!(error instanceof Error) && (typeof name !== 'string' || typeof stack !== 'string'))
            return [{}, false];
        const fields: Record<string, string> = {};
        const ctor: unknown = (Object.getPrototypeOf(error) as { constructor?: unknown } | null)
            ?.constructor;
        const type = [name, typeof ctor === 'function' ? ctor.name : undefined].find(
            (t): t is string => typeof t === 'string' && ERROR_TYPE_PATTERN.test(t),
        );
        if (type) fields[ERROR_TYPE_FIELD] = type;
        if (
            typeof stack !== 'string' ||
            !['string', 'undefined'].includes(typeof name) ||
            !['string', 'undefined'].includes(typeof message)
        )
            return [fields, false];
        // Frames start after the `Name: message` header (V8 formats it like Error#toString).
        // A header that no longer matches (message changed after capture) may hide message
        // text in frame-shaped lines, so then no frames are read at all.
        const label = (name as string | undefined) ?? 'Error';
        const text = (message as string | undefined) ?? '';
        const header = !label ? text : !text ? label : `${label}: ${text}`;
        if (
            !stack.startsWith(header) ||
            (stack.length > header.length && stack[header.length] !== '\n')
        )
            return [fields, false];
        const lines: string[] = [];
        for (const raw of stack.slice(header.length + 1).split('\n')) {
            const line = raw.trim();
            const named = NAMED_FRAME.exec(line);
            const match = named ?? ANONYMOUS_FRAME.exec(line);
            if (!match) continue;
            const [fn, path, lineNo] = named
                ? [functionName(match[1] ?? ''), match[2], match[3]]
                : ['<anonymous>', match[1], match[2]];
            const file = (path ?? '')
                .replace(/^file:\/\//, '')
                .replace(/[?#].*$/, '')
                .split(/[\\/]/)
                .pop();
            lines.push(`at ${fn} (${file}:${lineNo})`);
        }
        if (!lines.length) return [fields, false];
        const [trace, cut] = frames(lines);
        fields[STACKTRACE_FIELD] = trace;
        return [fields, cut];
    } catch {
        return [{}, false];
    }
}

/** Drop the outermost frame; remove the stack once one frame is left. */
function shrinkStack(record: Record<string, unknown>): boolean {
    const stack = record[STACKTRACE_FIELD];
    if (typeof stack !== 'string') return false;
    const end = stack.lastIndexOf('\n');
    if (end >= 0) record[STACKTRACE_FIELD] = stack.slice(0, end);
    else delete record[STACKTRACE_FIELD];
    return true;
}

/** Shorten the stack, then remove the largest custom fields, until the record fits. */
function fit(
    record: Record<string, unknown>,
    removable: Set<string>,
    dropped: number,
    truncated: boolean,
): void {
    const flagged = () => {
        if (truncated) record[TRUNCATED_FIELD] = true;
        // Clamped at the schema maximum so a high count never invalidates the record.
        if (dropped) record[DROPPED_FIELD] = Math.min(dropped, MAX_DROPPED_FIELD_COUNT);
        return record;
    };
    while (encodedBytes(flagged()) > MAX_RECORD_BYTES) {
        if (shrinkStack(record)) {
            truncated = true;
            continue;
        }
        let largest: string | undefined;
        let largestSize = -1;
        for (const key of removable) {
            if (!(key in record)) continue;
            const size = encodedBytes({ [key]: record[key] });
            if (
                size > largestSize ||
                (size === largestSize && largest !== undefined && key > largest)
            ) {
                largest = key;
                largestSize = size;
            }
        }
        if (largest === undefined) return; // Validation reports record_too_large; dropped.
        delete record[largest];
        removable.delete(largest);
        dropped++;
    }
}

/** One logger per process/sink. No global replacement, exporter, retry or private queue. */
export function createLogger(config: LogConfig, stream: Writable = process.stdout): JsonLogger {
    const identity = Object.freeze({
        service: config.service,
        environment: config.environment,
        region: config.region,
    });
    const errors = validateRecord({
        ...identity,
        timestamp: 0,
        level: 'INFO',
        message: 'Configuration check',
    });
    if (errors.length) throw new ContractViolation(errors);
    const names = config.allowedFields ?? [];
    if (
        !Array.isArray(names) ||
        names.length > 32 ||
        names.some(
            (k) =>
                typeof k !== 'string' ||
                !/^[A-Za-z][A-Za-z0-9._-]{0,127}$/.test(k) ||
                COMMON_FIELDS.includes(k),
        )
    ) {
        throw new Error('invalid_allowed_fields');
    }
    const allowed = new Set<string>(REQUEST_FIELDS);
    for (const name of config.allowedFields ?? []) allowed.add(name);
    const counts = { written: 0, invalid: 0, backpressure: 0, io: 0, closed: 0 };
    const pending = new Set<object>();
    let blocked = stream.writableNeedDrain;
    let failed = false;
    let closed = false;
    let notify: (() => void) | undefined;
    let flushing: Promise<boolean> | undefined;
    let closing: Promise<boolean> | undefined;

    const onDrain = () => {
        blocked = false;
    };
    const onError = () => {
        failed = true;
        counts.io += pending.size;
        pending.clear();
        notify?.();
    };
    const detach = () => {
        stream.off('drain', onDrain);
        stream.off('error', onError);
        stream.off('close', onStreamClose);
    };
    const onStreamClose = () => {
        onError();
        detach();
    };
    stream.on('drain', onDrain);
    stream.on('error', onError);
    stream.on('close', onStreamClose);

    const flush = (timeoutMs = 1000): Promise<boolean> => {
        if (!Number.isInteger(timeoutMs) || timeoutMs < 0 || timeoutMs > 30_000)
            return Promise.reject(new Error('invalid_flush_timeout'));
        if (flushing) return flushing;
        if (!pending.size) return Promise.resolve(!failed);
        flushing = new Promise<boolean>((resolve) => {
            const finish = (ok: boolean) => {
                clearTimeout(timer);
                notify = undefined;
                resolve(ok);
            };
            const timer = setTimeout(() => finish(false), timeoutMs);
            notify = () => {
                if (!pending.size) finish(!failed);
            };
        }).finally(() => {
            flushing = undefined;
        });
        return flushing;
    };

    return {
        log(message, options = {}) {
            if (closed) {
                counts.closed++;
                return false;
            }
            if (failed || stream.destroyed || !stream.writable) {
                counts.io++;
                return false;
            }
            // Honor Node's backpressure. Also cap outstanding callbacks at 128 * 4097 bytes.
            if (blocked || pending.size >= 128) {
                counts.backpressure++;
                return false;
            }
            try {
                // A non-string message has no text to keep: dropped as invalid.
                if (typeof message !== 'string') throw Error('invalid_message');
                const [text, cutMessage] = shorten(message, MAX_MESSAGE_BYTES);
                let truncated = cutMessage;
                let dropped = 0;
                const record: Record<string, unknown> = {
                    ...identity,
                    timestamp: BigInt(Date.now()) * 1_000_000n,
                    level: options.level ?? 'INFO',
                    message: text,
                };
                const traceId = currentTraceId();
                if (traceId) record.trace_id = traceId;
                for (const field of ['event', 'outcome'] as const) {
                    const value = options[field];
                    if (value === undefined) continue;
                    if (typeof value !== 'string' || value.length > MAX_RECORD_BYTES)
                        throw Error('invalid_event');
                    record[field] = value;
                }
                const custom = new Set<string>();
                if (options.fields !== undefined) {
                    if (
                        !options.fields ||
                        Object.getPrototypeOf(options.fields) !== Object.prototype
                    )
                        throw Error('invalid_fields');
                    const fields = Object.entries(Object.getOwnPropertyDescriptors(options.fields));
                    // Remove what cannot be emitted (unknown, protected, non-scalar, accessor,
                    // malformed Unicode, invalid error field); keep the record and count it.
                    for (const [key, descriptor] of fields) {
                        const value: unknown = descriptor.value;
                        if (
                            !allowed.has(key) ||
                            !('value' in descriptor) ||
                            !(
                                value === null ||
                                typeof value === 'boolean' ||
                                typeof value === 'string' ||
                                (typeof value === 'number' && Number.isFinite(value))
                            ) ||
                            (typeof value === 'string' && !value.isWellFormed()) ||
                            (key === ERROR_TYPE_FIELD &&
                                !(typeof value === 'string' && ERROR_TYPE_PATTERN.test(value))) ||
                            (key === STACKTRACE_FIELD && !(typeof value === 'string' && value))
                        ) {
                            dropped++;
                            continue;
                        }
                        if (typeof value === 'string') {
                            const [kept, cut] = shorten(
                                value,
                                key === STACKTRACE_FIELD ? MAX_STACKTRACE_BYTES : MAX_FIELD_BYTES,
                            );
                            record[key] = kept;
                            truncated ||= cut;
                        } else record[key] = value;
                        if (!REQUEST_FIELDS.includes(key)) custom.add(key);
                    }
                }
                Object.assign(record, currentRequestFields());
                if (options.error !== undefined) {
                    const [error, cut] = errorFields(options.error);
                    for (const [key, value] of Object.entries(error)) {
                        if (key in record) continue; // A caller-supplied value wins.
                        record[key] = value;
                        // Only the SDK's own stack can have been cut.
                        if (key === STACKTRACE_FIELD) truncated ||= cut;
                    }
                }
                fit(record, custom, dropped, truncated);
                // Independent/system events remain valid common records without a fabricated trace ID.
                const profile =
                    'request_event' in record
                        ? 'request'
                        : traceId && (options.event !== undefined || options.outcome !== undefined)
                          ? 'lifecycle'
                          : traceId
                            ? 'correlated'
                            : 'common';
                const line = encodeRecord(record, profile) + '\n';
                const token = {};
                pending.add(token);
                try {
                    blocked = !stream.write(line, (error) => {
                        if (!pending.delete(token)) return;
                        if (error) {
                            counts.io++;
                            failed = true;
                        } else counts.written++;
                        notify?.();
                        // Keep the error listener through the stream's asynchronous error event.
                        if (closed && !pending.size) setImmediate(detach);
                    });
                } catch {
                    if (pending.delete(token)) counts.io++;
                    failed = true;
                    notify?.();
                    return false;
                }
                return true;
            } catch {
                counts.invalid++;
                return false;
            }
        },
        stats: () => Object.freeze({ ...counts, pending: pending.size }),
        flush,
        close(timeoutMs = 1000) {
            if (closing) return closing;
            closed = true;
            closing = flush(timeoutMs).then((ok) => {
                // Never end/destroy a caller-owned stream (including stdout).
                // Timed-out writes keep one listener until completion/stream close to catch late errors.
                if (!pending.size) setImmediate(detach);
                return ok;
            });
            return closing;
        },
    };
}

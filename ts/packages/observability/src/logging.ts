import type { Writable } from 'node:stream';
import {
    COMMON_FIELDS,
    MAX_MESSAGE_BYTES,
    MAX_RECORD_BYTES,
    ContractViolation,
    encodeRecord,
    validateRecord,
} from './rules.js';
import { currentTraceId } from './context.js';

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
    const allowed = new Set(names);
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
                const record: Record<string, unknown> = {
                    ...identity,
                    timestamp: BigInt(Date.now()) * 1_000_000n,
                    level: options.level ?? 'INFO',
                    message,
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
                if (options.fields !== undefined) {
                    if (
                        !options.fields ||
                        Object.getPrototypeOf(options.fields) !== Object.prototype
                    )
                        throw Error('invalid_fields');
                    const fields = Object.getOwnPropertyDescriptors(options.fields);
                    if (Object.keys(fields).length > 32) throw Error('invalid_fields');
                    for (const [key, descriptor] of Object.entries(fields)) {
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
                            (typeof value === 'string' && value.length > MAX_RECORD_BYTES)
                        )
                            throw Error('invalid_fields');
                        record[key] = value;
                    }
                }
                if (typeof message !== 'string' || message.length > MAX_MESSAGE_BYTES)
                    throw Error('invalid_message');
                // Independent/system events remain valid common records without a fabricated trace ID.
                const profile =
                    traceId && (options.event !== undefined || options.outcome !== undefined)
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

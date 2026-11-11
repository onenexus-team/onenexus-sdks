import type { Meter, ObservableCounter } from '@opentelemetry/api';

/**
 * One drop metric (design review R1, tests/logging/scenarios.json `drop_metric`): every line
 * a logger does not write is counted once, process-wide, per (service, reason).
 */
export const DROP_REASONS = ['closed', 'invalid', 'io_errors', 'queue_full'] as const;
export type DropReason = (typeof DROP_REASONS)[number];
export interface DropCount {
    readonly service: string;
    readonly reason: DropReason;
    readonly count: number;
}

const OTEL_NAME = 'onenexus.log.records.dropped';
const OTEL_UNIT = '{record}';
const PROMETHEUS_NAME = 'onenexus_log_records_dropped_total';
const HELP = 'Log records the logging SDK did not write, by reason.';

// Process-wide totals; they never decrease and outlive the loggers that add to them.
const totals = new Map<string, Record<DropReason, number>>();

/**
 * Registers all four reasons for `service` at 0 and returns the function a logger calls
 * for every line it does not write. Internal: not exported from the package.
 */
export function dropCounter(service: string): (reason: DropReason, lines: number) => void {
    let row = totals.get(service);
    if (!row) {
        row = { closed: 0, invalid: 0, io_errors: 0, queue_full: 0 };
        totals.set(service, row);
    }
    const counts = row;
    return (reason, lines) => {
        counts[reason] += lines;
    };
}

const compare = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
const sorted = (counts: readonly DropCount[]) =>
    [...counts].sort((a, b) => compare(a.service, b.service) || compare(a.reason, b.reason));

/** Snapshot of the process-wide drop counts, sorted by service then reason. */
export function logDropCounts(): readonly DropCount[] {
    const rows: DropCount[] = [];
    for (const [service, counts] of totals)
        for (const reason of DROP_REASONS) rows.push({ service, reason, count: counts[reason] });
    return sorted(rows);
}

const escapeLabel = (value: string) =>
    value.replaceAll('\\', '\\\\').replaceAll('"', '\\"').replaceAll('\n', '\\n');

/** Prometheus text exposition of `counts` (default: the live snapshot), for a /metrics route. */
export function dropMetricsText(counts: readonly DropCount[] = logDropCounts()): string {
    let text = `# HELP ${PROMETHEUS_NAME} ${HELP}\n# TYPE ${PROMETHEUS_NAME} counter\n`;
    for (const { service, reason, count } of sorted(counts))
        text += `${PROMETHEUS_NAME}{service="${escapeLabel(service)}",reason="${escapeLabel(reason)}"} ${count}\n`;
    return text;
}

/** Registers the asynchronous counter on the service's meter; one observation per snapshot row. */
export function registerDropMetric(meter: Meter): ObservableCounter {
    const counter = meter.createObservableCounter(OTEL_NAME, {
        unit: OTEL_UNIT,
        description: HELP,
    });
    counter.addCallback((result) => {
        for (const { service, reason, count } of logDropCounts())
            result.observe(count, { service, reason });
    });
    return counter;
}

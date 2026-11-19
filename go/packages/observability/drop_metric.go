package observability

// One drop metric (design review R1; tests/logging/scenarios.json drop_metric).
// Every line a handler does not write is counted once, process-wide, per
// (service, reason). The counts are read as a snapshot, as Prometheus text, or
// through an OpenTelemetry asynchronous counter.

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
	"sync/atomic"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
)

const (
	// DropMetricOTelName is the OpenTelemetry instrument name.
	DropMetricOTelName = "onenexus.log.records.dropped"
	// DropMetricUnit is the OpenTelemetry instrument unit.
	DropMetricUnit = "{record}"
	// DropMetricPrometheusName is the exposition name of the counter.
	DropMetricPrometheusName = "onenexus_log_records_dropped_total"
	// DropMetricHelp is the HELP text and the instrument description.
	DropMetricHelp = "Log records the logging SDK did not write, by reason."
)

// DropReason is a write-model counter that means "not written".
type DropReason string

// The reasons, in their sorted (exposition) order.
const (
	DropClosed    DropReason = "closed"
	DropInvalid   DropReason = "invalid"
	DropIOErrors  DropReason = "io_errors"
	DropQueueFull DropReason = "queue_full"
)

// dropReasons is indexed like serviceDrops.
var dropReasons = [...]DropReason{DropClosed, DropInvalid, DropIOErrors, DropQueueFull}

type reasonIndex int

const (
	reasonClosed reasonIndex = iota
	reasonInvalid
	reasonIOErrors
	reasonQueueFull
)

// DropCount is one row: the lines a service's handlers did not write for one reason.
type DropCount struct {
	Service string
	Reason  DropReason
	Count   uint64
}

// serviceDrops are one service's process-wide counters. A handler keeps a
// pointer, so counting takes no lock.
type serviceDrops [len(dropReasons)]atomic.Uint64

var drops = struct {
	mu        sync.Mutex // guards the map only; never held while counting
	byService map[string]*serviceDrops
}{byService: map[string]*serviceDrops{}}

// registerDrops returns the counters of service, creating them at 0, so every
// reason is reported from the service's first handler on.
func registerDrops(service string) *serviceDrops {
	drops.mu.Lock()
	defer drops.mu.Unlock()
	d := drops.byService[service]
	if d == nil {
		d = &serviceDrops{}
		drops.byService[service] = d
	}
	return d
}

// DropCounts returns every (service, reason) row, sorted by service then reason.
func DropCounts() []DropCount {
	drops.mu.Lock()
	services := make(map[string]*serviceDrops, len(drops.byService))
	for service, d := range drops.byService {
		services[service] = d
	}
	drops.mu.Unlock()
	rows := make([]DropCount, 0, len(services)*len(dropReasons))
	for service, d := range services {
		for i, reason := range dropReasons {
			rows = append(rows, DropCount{service, reason, d[i].Load()})
		}
	}
	sortDropCounts(rows)
	return rows
}

func sortDropCounts(rows []DropCount) {
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].Service != rows[j].Service {
			return rows[i].Service < rows[j].Service
		}
		return rows[i].Reason < rows[j].Reason
	})
}

var labelEscaper = strings.NewReplacer(`\`, `\\`, `"`, `\"`, "\n", `\n`)

// DropMetricsText is the Prometheus text exposition of the live counts.
func DropMetricsText() string { return FormatDropMetrics(DropCounts()) }

// FormatDropMetrics is the Prometheus text exposition of counts: HELP and TYPE
// first, rows sorted by service then reason, label values escaped.
func FormatDropMetrics(counts []DropCount) string {
	rows := append([]DropCount(nil), counts...)
	sortDropCounts(rows)
	var b strings.Builder
	fmt.Fprintf(&b, "# HELP %s %s\n# TYPE %s counter\n", DropMetricPrometheusName, DropMetricHelp, DropMetricPrometheusName)
	for _, row := range rows {
		fmt.Fprintf(&b, "%s{service=\"%s\",reason=\"%s\"} %d\n", DropMetricPrometheusName,
			labelEscaper.Replace(row.Service), labelEscaper.Replace(string(row.Reason)), row.Count)
	}
	return b.String()
}

// RegisterDropMetric creates the asynchronous monotonic counter
// DropMetricOTelName on meter; each collection observes every DropCounts row.
func RegisterDropMetric(meter metric.Meter) (metric.Int64ObservableCounter, error) {
	return meter.Int64ObservableCounter(DropMetricOTelName,
		metric.WithUnit(DropMetricUnit),
		metric.WithDescription(DropMetricHelp),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			for _, row := range DropCounts() {
				o.Observe(int64(row.Count), metric.WithAttributes(
					attribute.String("service", row.Service), attribute.String("reason", string(row.Reason))))
			}
			return nil
		}))
}

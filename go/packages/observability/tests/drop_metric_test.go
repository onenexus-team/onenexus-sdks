package observability_test

// One drop metric (tests/logging/scenarios.json drop_metric, design review R1).
// The counts are process-wide, so every test uses its own service names.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"reflect"
	"strings"
	"testing"

	obs "github.com/onenexus-team/onenexus-sdks/go/packages/observability"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/metric/metricdata"
)

type dropMetricSpec struct {
	OTelName       string   `json:"otel_name"`
	OTelUnit       string   `json:"otel_unit"`
	PrometheusName string   `json:"prometheus_name"`
	Reasons        []string `json:"reasons"`
	Help           string   `json:"help"`
	Example        struct {
		Counts []struct {
			Service string `json:"service"`
			Reason  string `json:"reason"`
			Count   uint64 `json:"count"`
		} `json:"counts"`
		Text string `json:"text"`
	} `json:"prometheus_text_example"`
}

func loadDropMetric(t *testing.T) dropMetricSpec {
	t.Helper()
	path := os.Getenv("ONENEXUS_LOGGING_SCENARIOS")
	if path == "" {
		path = "../../../../tests/logging/scenarios.json"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var doc struct {
		DropMetric dropMetricSpec `json:"drop_metric"`
	}
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	return doc.DropMetric
}

func serviceConfig(service string) obs.Config {
	c := config()
	c.Service = service
	return c
}

// rows returns service's rows as reason -> count.
func rows(service string) map[obs.DropReason]uint64 {
	got := map[obs.DropReason]uint64{}
	for _, row := range obs.DropCounts() {
		if row.Service == service {
			got[row.Reason] = row.Count
		}
	}
	return got
}

func zeroRows() map[obs.DropReason]uint64 {
	return map[obs.DropReason]uint64{obs.DropClosed: 0, obs.DropInvalid: 0, obs.DropIOErrors: 0, obs.DropQueueFull: 0}
}

func TestDropMetricConstantsMatchSharedSpec(t *testing.T) {
	spec := loadDropMetric(t)
	if spec.OTelName != obs.DropMetricOTelName || spec.OTelUnit != obs.DropMetricUnit ||
		spec.PrometheusName != obs.DropMetricPrometheusName || spec.Help != obs.DropMetricHelp {
		t.Fatal("constants differ from scenarios.json", spec)
	}
	got := []string{string(obs.DropClosed), string(obs.DropInvalid), string(obs.DropIOErrors), string(obs.DropQueueFull)}
	if !reflect.DeepEqual(got, spec.Reasons) {
		t.Fatal("reasons", got, spec.Reasons)
	}
}

// every_reason_reported_from_first_handler
func TestDropEveryReasonReportedFromFirstHandler(t *testing.T) {
	service := t.Name()
	if len(rows(service)) != 0 {
		t.Fatal("rows before any handler")
	}
	h, _ := newSyncHandler(t, serviceConfig(service))
	defer h.Close()
	if got := rows(service); !reflect.DeepEqual(got, zeroRows()) {
		t.Fatal(got)
	}
	var order []obs.DropReason // DropCounts is sorted by service, then reason
	for _, row := range obs.DropCounts() {
		if row.Service == service {
			order = append(order, row.Reason)
		}
	}
	if want := []obs.DropReason{obs.DropClosed, obs.DropInvalid, obs.DropIOErrors, obs.DropQueueFull}; !reflect.DeepEqual(order, want) {
		t.Fatal("order", order)
	}
}

// each_reason_counted
func TestDropEachReasonCounted(t *testing.T) {
	service := t.Name()

	h, _ := newSyncHandler(t, serviceConfig(service))
	logger := slog.New(h)
	logger.Info("bad \xff utf-8") // invalid
	h.Close()
	logger.Info("after close") // closed
	s := h.Stats()

	failing := &firstWriter{fail: func(*firstWriter, []byte) (int, error) { return 0, errors.New("private-sentinel") }}
	h2, err := obs.NewHandler(serviceConfig(service), failing)
	if err != nil {
		t.Fatal(err)
	}
	emit(t, h2, 2) // io_errors
	h2.Close()
	s2 := h2.Stats()

	gate := newGate()
	h3, err := obs.NewHandler(serviceConfig(service), gate)
	if err != nil {
		t.Fatal(err)
	}
	emit(t, h3, obs.QueueCapacity+10) // queue_full
	s3 := h3.Stats()
	close(gate.open)
	h3.Close()

	want := map[obs.DropReason]uint64{
		obs.DropInvalid: s.Invalid, obs.DropClosed: s.Closed + s2.Closed + s3.Closed,
		obs.DropIOErrors: s2.IOErrors, obs.DropQueueFull: s3.Busy,
	}
	if s.Invalid != 1 || s.Closed != 1 || s2.IOErrors != 1 || s3.Busy == 0 {
		t.Fatal("stats", s, s2, s3)
	}
	if got := rows(service); !reflect.DeepEqual(got, want) {
		t.Fatal(got, want)
	}
}

// handlers_of_one_service_are_summed
func TestDropHandlersOfOneServiceAreSummed(t *testing.T) {
	service := t.Name()
	a, _ := newSyncHandler(t, serviceConfig(service))
	b, _ := newSyncHandler(t, serviceConfig(service))
	a.Close()
	b.Close()
	emit(t, a, 2)
	emit(t, b, 3)
	got := rows(service)
	if len(got) != 4 || got[obs.DropClosed] != a.Stats().Closed+b.Stats().Closed || got[obs.DropClosed] != 5 {
		t.Fatal(got)
	}
}

// services_are_separate
func TestDropServicesAreSeparate(t *testing.T) {
	one, other := t.Name()+"-one", t.Name()+"-other"
	a, _ := newSyncHandler(t, serviceConfig(one))
	b, _ := newSyncHandler(t, serviceConfig(other))
	defer b.Close()
	a.Close()
	emit(t, a, 1)
	if got := rows(one)[obs.DropClosed]; got != 1 {
		t.Fatal(got)
	}
	if got := rows(other); !reflect.DeepEqual(got, zeroRows()) {
		t.Fatal(got)
	}
}

// counts_survive_close
func TestDropCountsSurviveClose(t *testing.T) {
	service := t.Name()
	h, _ := newSyncHandler(t, serviceConfig(service))
	slog.New(h).Info("bad \xff")
	before := rows(service)
	h.Close()
	after := rows(service)
	if len(after) != 4 || after[obs.DropInvalid] != 1 {
		t.Fatal(after)
	}
	for reason, count := range before {
		if after[reason] < count {
			t.Fatal("decreased", reason)
		}
	}
}

// prometheus_text_format
func TestDropPrometheusTextFormat(t *testing.T) {
	spec := loadDropMetric(t)
	counts := make([]obs.DropCount, 0, len(spec.Example.Counts))
	for _, c := range spec.Example.Counts {
		counts = append(counts, obs.DropCount{Service: c.Service, Reason: obs.DropReason(c.Reason), Count: c.Count})
	}
	if got := obs.FormatDropMetrics(counts); got != spec.Example.Text {
		t.Fatalf("got\n%q\nwant\n%q", got, spec.Example.Text)
	}
	if counts[0].Service != "svc-b" {
		t.Fatal("FormatDropMetrics reordered its argument")
	}
	service := t.Name()
	h, _ := newSyncHandler(t, serviceConfig(service))
	defer h.Close()
	live := obs.DropMetricsText()
	row := fmt.Sprintf("%s{service=%q,reason=\"queue_full\"} 0\n", obs.DropMetricPrometheusName, service)
	if !strings.HasPrefix(live, "# HELP ") || !strings.Contains(live, row) {
		t.Fatal(live)
	}
}

// otel_asynchronous_counter
func TestDropOTelAsynchronousCounter(t *testing.T) {
	service := t.Name()
	h, _ := newSyncHandler(t, serviceConfig(service))
	h.Close()
	emit(t, h, 2)

	reader := sdkmetric.NewManualReader()
	provider := sdkmetric.NewMeterProvider(sdkmetric.WithReader(reader))
	defer func() { _ = provider.Shutdown(context.Background()) }()
	if _, err := obs.RegisterDropMetric(provider.Meter("test")); err != nil {
		t.Fatal(err)
	}
	var rm metricdata.ResourceMetrics
	if err := reader.Collect(context.Background(), &rm); err != nil {
		t.Fatal(err)
	}
	if len(rm.ScopeMetrics) != 1 || len(rm.ScopeMetrics[0].Metrics) != 1 {
		t.Fatal("want one instrument", rm)
	}
	m := rm.ScopeMetrics[0].Metrics[0]
	sum, ok := m.Data.(metricdata.Sum[int64])
	if m.Name != obs.DropMetricOTelName || m.Unit != obs.DropMetricUnit || !ok || !sum.IsMonotonic ||
		sum.Temporality != metricdata.CumulativeTemporality {
		t.Fatal("instrument", m.Name, m.Unit, m.Data)
	}
	type key struct{ service, reason string }
	got := map[key]int64{}
	for _, p := range sum.DataPoints {
		s, _ := p.Attributes.Value("service")
		r, _ := p.Attributes.Value("reason")
		if p.Attributes.Len() != 2 {
			t.Fatal("attributes", p.Attributes)
		}
		got[key{s.AsString(), r.AsString()}] = p.Value
	}
	want := map[key]int64{}
	for _, row := range obs.DropCounts() {
		want[key{row.Service, string(row.Reason)}] = int64(row.Count)
	}
	if !reflect.DeepEqual(got, want) || got[key{service, "closed"}] != 2 {
		t.Fatal(got)
	}
}

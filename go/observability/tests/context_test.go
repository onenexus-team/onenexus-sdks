package observability_test

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"reflect"
	"strings"
	"sync"
	"testing"

	obs "github.com/onenexus-team/onenexus-sdks/go/observability"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	"go.opentelemetry.io/otel/trace"
)

const traceA = "11111111111111111111111111111111"
const traceB = "33333333333333333333333333333333"
const parent = "00-" + traceA + "-2222222222222222-01"

func headers(value string) http.Header { return http.Header{"Traceparent": []string{value}} }

func TestSharedCases(t *testing.T) {
	path := os.Getenv("ONENEXUS_LOGGING_SCENARIOS")
	if path == "" {
		path = "../../../tests/logging/scenarios.json"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var vectors struct {
		Records []struct {
			ID, Profile string
			Record      json.RawMessage
			Errors      []string
		} `json:"record_cases"`
		Contexts []struct {
			ID, Traceparent string
			Trusted         bool
			Preserve        bool `json:"preserve_trace"`
		} `json:"context_cases"`
	}
	if err = json.Unmarshal(data, &vectors); err != nil {
		t.Fatal(err)
	}
	results := make([]map[string]any, 0)
	for _, c := range vectors.Records {
		got := obs.ValidateJSON(c.Record, c.Profile)
		if !reflect.DeepEqual(got, c.Errors) {
			t.Fatalf("%s: %v want %v", c.ID, got, c.Errors)
		}
		results = append(results, map[string]any{"kind": "record", "id": c.ID, "errors": got})
	}
	root := context.Background()
	seen := map[string]bool{}
	for _, c := range vectors.Contexts {
		ctx := obs.EdgeContext(root, headers(c.Traceparent), c.Trusted)
		id := obs.TraceID(ctx)
		if c.Preserve && id != traceA || !c.Preserve && (id == traceA || seen[id]) || id == "" {
			t.Fatal("edge policy failed:", c.ID)
		}
		seen[id] = true
		if obs.TraceID(root) != "" {
			t.Fatal("parent context mutated")
		}
		results = append(results, map[string]any{"kind": "context", "id": c.ID, "trace_id": id, "outgoing_traceparent": obs.OutgoingHeaders(ctx).Get("traceparent"), "after_trace_id": nil})
	}
	if path := os.Getenv("ONENEXUS_LOGGING_RESULTS"); path != "" {
		data, err := json.Marshal(map[string]any{"adapter_protocol": 1, "results": results})
		if err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(path, data, 0600); err != nil {
			t.Fatal(err)
		}
	}
}

func TestServiceBoundaryDoesNotMintIDs(t *testing.T) {
	outer := obs.IncomingContext(context.Background(), headers(parent), true)
	cases := []http.Header{{"Traceparent": {}, "traceparent": {parent}}, nil, headers("bad"), headers(parent + "\n"), headers(strings.Replace(parent, traceA, strings.Repeat("0", 32), 1)), headers(strings.Replace(parent, traceA, strings.Repeat("A", 32), 1)), {"traceparent": {parent}, "Traceparent": {parent}}, {"traceparent": {parent, parent}}}
	for _, h := range cases {
		ctx := obs.IncomingContext(outer, h, true)
		if obs.TraceID(ctx) != "" || len(obs.OutgoingHeaders(ctx)) != 0 {
			t.Fatal("inherited invalid trace")
		}
	}
	if obs.TraceID(obs.IncomingContext(outer, headers(parent), false)) != "" {
		t.Fatal("public trace trusted")
	}
	h := headers(parent)
	h.Set("baggage", "private-sentinel")
	h.Set("tracestate", "private-sentinel")
	ctx := obs.IncomingContext(context.Background(), h, true)
	if got := obs.OutgoingHeaders(ctx); len(got) != 1 || got.Get("traceparent") != parent {
		t.Fatal("unsafe outgoing headers")
	}
	if obs.TraceID(outer) != traceA {
		t.Fatal("parent changed")
	}
}

func TestConcurrentCancellationPanicAndReusedWorker(t *testing.T) {
	root := context.Background()
	ready := make(chan struct{}, 2)
	release := make(chan struct{})
	var wg sync.WaitGroup
	for _, id := range []string{traceA, traceB} {
		wg.Add(1)
		go func(id string) {
			defer wg.Done()
			ctx := obs.IncomingContext(root, headers(strings.Replace(parent, traceA, id, 1)), true)
			ready <- struct{}{}
			<-release
			if obs.TraceID(ctx) != id {
				t.Error("concurrent leak")
			}
			cancelled, cancel := context.WithCancel(ctx)
			cancel()
			if cancelled.Err() != context.Canceled || obs.TraceID(cancelled) != id {
				t.Error("cancellation lost")
			}
			func() { defer func() { _ = recover() }(); _ = obs.UncorrelatedContext(ctx); panic("test") }()
			if obs.TraceID(ctx) != id {
				t.Error("panic changed parent")
			}
		}(id)
	}
	<-ready
	<-ready
	close(release)
	wg.Wait()
	if obs.TraceID(root) != "" {
		t.Fatal("reused worker leaked trace")
	}
}

func TestDurableMetadataRetryAndRealRecordedChild(t *testing.T) {
	ctx := obs.IncomingContext(context.Background(), headers(parent), true)
	data, _ := json.Marshal(obs.OutgoingHeaders(ctx))
	var saved http.Header
	if json.Unmarshal(data, &saved) != nil {
		t.Fatal("metadata")
	}
	exporter := tracetest.NewInMemoryExporter()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSyncer(exporter), sdktrace.WithSampler(sdktrace.AlwaysSample()))
	defer provider.Shutdown(context.Background())
	for range 2 {
		worker := obs.IncomingContext(context.Background(), saved, true)
		child, span := provider.Tracer("test").Start(worker, "attempt")
		if !span.IsRecording() || obs.TraceID(child) != traceA || obs.OutgoingHeaders(child).Get("traceparent") == parent {
			t.Fatal("child compatibility")
		}
		if obs.OutgoingHeaders(obs.IncomingContext(child, saved, true)).Get("traceparent") != obs.OutgoingHeaders(child).Get("traceparent") {
			t.Fatal("child span overwritten")
		}
		// Independent work stays uncorrelated even if another library starts a span.
		independent := obs.UncorrelatedContext(child)
		independent, other := provider.Tracer("test").Start(independent, "independent")
		if obs.TraceID(independent) != "" {
			t.Fatal("uncorrelated boundary bypassed")
		}
		other.End()
		span.End()
	}
	spans := exporter.GetSpans()
	if len(spans) != 4 || spans[1].SpanContext.SpanID() == spans[3].SpanContext.SpanID() {
		t.Fatal("attempt IDs not distinct")
	}
	for _, i := range []int{1, 3} {
		if spans[i].Parent.TraceID().String() != traceA {
			t.Fatal("parent lost")
		}
	}
	// Native OTel contexts work without a wrapper and unrelated ambient contexts cannot win.
	tid, _ := trace.TraceIDFromHex(traceB)
	sid, _ := trace.SpanIDFromHex("4444444444444444")
	native := trace.ContextWithSpanContext(ctx, trace.NewSpanContext(trace.SpanContextConfig{TraceID: tid, SpanID: sid}))
	if obs.TraceID(native) != traceA {
		t.Fatal("unrelated child bypassed boundary")
	}
}

package observability_test

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"math"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	obs "github.com/onenexus-team/onenexus-sdks/go/packages/observability"
)

func config() obs.Config {
	return obs.Config{Service: "go-service", Environment: "development", Region: "ric1", AllowedFields: []string{"example.attempt", "job.id"}, MinLevel: slog.Level(-8)}
}
func record(message string, attrs ...slog.Attr) slog.Record {
	r := slog.NewRecord(time.Unix(1, 42), slog.LevelInfo, message, 0)
	r.AddAttrs(attrs...)
	return r
}

func TestHandlerSchemaLevelsAndImmutableClones(t *testing.T) {
	h, output := newSyncHandler(t, config())
	defaultLogger := slog.Default()
	logger := slog.New(h)
	logger.Info("System ready")
	ctx := obs.IncomingContext(context.Background(), headers(parent), true)
	for _, level := range []slog.Level{-8, -4, 0, 4, 8, 12} {
		logger.LogAttrs(ctx, level, "Work completed", slog.String("event", "work.completed"), slog.String("outcome", "success"), slog.Int("example.attempt", 1))
	}
	child := logger.WithGroup("job").With("id", "job-1")
	child.InfoContext(ctx, "Child")
	logger.InfoContext(ctx, "Parent")
	if slog.Default() != defaultLogger {
		t.Fatal("global logger changed")
	}
	lines := bytes.Split(bytes.TrimSpace(output.Bytes()), []byte{'\n'})
	if len(lines) != 9 || h.Stats().Written != 9 {
		t.Fatal("missing records", h.Stats())
	}
	for i, line := range lines {
		profile := "common"
		if i > 0 {
			profile = "correlated"
		}
		if i > 0 && i < 7 {
			profile = "lifecycle"
		}
		if got := obs.ValidateJSON(line, profile); len(got) != 0 {
			t.Fatal(got)
		}
		var row map[string]json.RawMessage
		_ = json.Unmarshal(line, &row)
		if i == 8 && row["job.id"] != nil {
			t.Fatal("clone mutated parent")
		}
	}
	h.Close()
	child.Info("Closed")
	h.Close()
	if h.Stats().Closed != 1 || h.Stats().Written != 9 {
		t.Fatal("close not shared")
	}
	if _, err := output.Write([]byte("caller still owns writer")); err != nil {
		t.Fatal(err)
	}
}

type unsafeValue struct{}

func (unsafeValue) LogValue() slog.Value { panic("must not evaluate application code") }

func TestInvalidRecordsAndConfigNeverLeak(t *testing.T) {
	for _, c := range []obs.Config{{}, {Service: "x", Environment: "dev", Region: "r"}, {Service: "x", Environment: "prod", Region: "r", AllowedFields: []string{"trace_id"}}, {Service: "x", Environment: "prod", Region: "r", AllowedFields: []string{"example.x", "example.x"}}} {
		if _, err := obs.NewHandler(c, io.Discard); err == nil {
			t.Fatal("invalid config accepted")
		}
	}
	if _, err := obs.NewHandler(config(), nil); err == nil {
		t.Fatal("nil writer accepted")
	}
	// MaxWait is deprecated and ignored; old values are still accepted.
	for wait, ok := range map[time.Duration]bool{time.Second: true, -1: false, 2 * time.Second: false} {
		c := config()
		c.MaxWait = wait
		if h, err := obs.NewHandler(c, io.Discard); (err == nil) != ok {
			t.Fatal("MaxWait validation changed", wait)
		} else if h != nil {
			h.Close()
		}
	}
	h, output := newSyncHandler(t, config())
	defer h.Close()
	// Only records that break a base-field rule are still dropped.
	cases := []slog.Record{
		slog.NewRecord(time.Date(3000, 1, 1, 0, 0, 0, 0, time.UTC), slog.LevelInfo, "invalid timestamp", 0), record(""), record(string([]byte{0xff})),
		record("safe", slog.String("event", "work.completed")),
	}
	for _, r := range cases {
		if err := h.Handle(context.Background(), r); err == nil {
			t.Fatal("invalid record accepted")
		}
	}
	if output.Len() != 0 || h.Stats().Invalid != uint64(len(cases)) {
		t.Fatal("invalid records leaked")
	}
	// Everything else keeps the line, without the offending value.
	kept := []struct {
		record    slog.Record
		truncated bool
		dropped   float64
		attempt   any
	}{
		{record(strings.Repeat("x", 1025)), true, 0, nil},
		{record("safe", slog.String("authorization", "private-sentinel")), false, 1, nil},
		{record("safe", slog.String("trace_id", traceB)), false, 1, nil},
		{record("safe", slog.Float64("example.attempt", math.NaN())), false, 1, nil},
		{record("safe", slog.Any("example.attempt", unsafeValue{})), false, 1, nil},
		{record("safe", slog.Any("example.attempt", map[string]string{"secret": "private-sentinel"})), false, 1, nil},
		{record("safe", slog.Int("example.attempt", 1), slog.Int("example.attempt", 2)), false, 1, float64(1)},
		{record("safe", slog.String("example.attempt", strings.Repeat("x", 1025))), true, 0, strings.Repeat("x", 1021) + "…"},
	}
	for _, c := range kept {
		output.Reset()
		if err := h.Handle(context.Background(), c.record); err != nil {
			t.Fatal(err)
		}
		row := keptRow(t, output.Bytes(), "common")
		if strings.Contains(output.String(), "sentinel") || row["trace_id"] != nil || row["example.attempt"] != c.attempt {
			t.Fatal("unsafe value emitted", output.String())
		}
		if (row["logging.truncated"] == true) != c.truncated || flagCount(row) != c.dropped {
			t.Fatal("missing degradation flags", output.String())
		}
	}
	// A bad clone attribute or group name never disables the derived logger.
	for _, handler := range []slog.Handler{h.WithAttrs([]slog.Attr{slog.String("service", "override")}), h.WithGroup(strings.Repeat("x", 129)).WithAttrs([]slog.Attr{slog.Int("example.attempt", 1)})} {
		for range 2 {
			output.Reset()
			if err := handler.Handle(context.Background(), record("clone")); err != nil {
				t.Fatal(err)
			}
			if row := keptRow(t, output.Bytes(), "common"); row["service"] != "go-service" || flagCount(row) != 1 {
				t.Fatal("bad clone attribute emitted", output.String())
			}
		}
	}
	if h.Stats().Invalid != uint64(len(cases)) {
		t.Fatal("kept records counted as invalid", h.Stats())
	}
	if !h.Enabled(context.Background(), slog.Level(-8)) || h.Enabled(context.Background(), slog.Level(-9)) {
		t.Fatal("level filter")
	}
}

func BenchmarkHandler(b *testing.B) {
	h, _ := obs.NewHandler(config(), io.Discard)
	ctx := obs.IncomingContext(context.Background(), headers(parent), true)
	r := record("Work completed", slog.Int("example.attempt", 1))
	b.ReportAllocs()
	b.ResetTimer()
	for range b.N {
		_ = h.Handle(ctx, r)
	}
}

func TestConcurrentWritesAreCompleteLines(t *testing.T) {
	h, output := newSyncHandler(t, config())
	defer h.Close()
	ready := make(chan struct{}, 64)
	start := make(chan struct{})
	var wg sync.WaitGroup
	for i := range 64 {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			ready <- struct{}{}
			<-start
			ctx := obs.IncomingContext(context.Background(), headers(parent), true)
			if err := h.Handle(ctx, record("Concurrent", slog.Int("example.attempt", n))); err != nil {
				t.Error(err)
			}
		}(i)
	}
	for range 64 {
		<-ready
	}
	close(start)
	wg.Wait()
	lines := bytes.Split(bytes.TrimSpace(output.Bytes()), []byte{'\n'})
	if len(lines) != 64 || h.Stats().Written != 64 || h.Stats().Busy != 0 {
		t.Fatal(h.Stats())
	}
	for _, line := range lines {
		if got := obs.ValidateJSON(line, "correlated"); len(got) != 0 {
			t.Fatal(got)
		}
	}
}

func TestSharedEmissionScenarios(t *testing.T) {
	path := os.Getenv("ONENEXUS_LOGGING_SCENARIOS")
	if path == "" {
		path = "../../../../tests/logging/scenarios.json"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var suite struct {
		Cases []struct {
			ID, Message string
			Traceparent *string
			Expected    map[string]any
			Absent      []string
		} `json:"emission_cases"`
	}
	if err = json.Unmarshal(data, &suite); err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) == 0 {
		t.Fatal("no shared emission scenarios")
	}
	for _, c := range suite.Cases {
		t.Run(c.ID, func(t *testing.T) {
			h, output := newSyncHandler(t, obs.Config{Service: "shared-test", Environment: "development", Region: "region-1"})
			defer h.Close()
			ctx := context.Background()
			if c.Traceparent != nil {
				ctx = obs.IncomingContext(ctx, headers(*c.Traceparent), true)
			}
			slog.New(h).InfoContext(ctx, c.Message)
			var row map[string]any
			if err = json.Unmarshal(output.Bytes(), &row); err != nil {
				t.Fatal(err)
			}
			for key, want := range c.Expected {
				if row[key] != want {
					t.Fatalf("%s: %v want %v", key, row[key], want)
				}
			}
			for _, key := range c.Absent {
				if _, ok := row[key]; ok {
					t.Fatal("unexpected", key)
				}
			}
			if len(obs.ValidateJSON(output.Bytes(), "common")) != 0 {
				t.Fatal("invalid output")
			}
		})
	}
}

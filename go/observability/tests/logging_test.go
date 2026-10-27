package observability_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"math"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	contract "github.com/onenexus-team/onenexus-sdks/contracts/log-correlation"
	obs "github.com/onenexus-team/onenexus-sdks/go/observability"
)

func config() obs.Config {
	return obs.Config{Service: "go-service", Environment: "development", Region: "ric1", AllowedFields: []string{"attempt", "job.id"}, MinLevel: slog.Level(-8)}
}
func record(message string, attrs ...slog.Attr) slog.Record {
	r := slog.NewRecord(time.Unix(1, 42), slog.LevelInfo, message, 0)
	r.AddAttrs(attrs...)
	return r
}

func TestHandlerSchemaLevelsAndImmutableClones(t *testing.T) {
	var output bytes.Buffer
	h, err := obs.NewHandler(config(), &output)
	if err != nil {
		t.Fatal(err)
	}
	defaultLogger := slog.Default()
	logger := slog.New(h)
	logger.Info("System ready")
	ctx := obs.IncomingContext(context.Background(), headers(parent), true)
	for _, level := range []slog.Level{-8, -4, 0, 4, 8, 12} {
		logger.LogAttrs(ctx, level, "Work completed", slog.String("event", "work.completed"), slog.String("outcome", "success"), slog.Int("attempt", 1))
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
		if got := contract.ValidateJSON(line, profile); len(got) != 0 {
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
	if _, err = output.WriteString("caller still owns writer"); err != nil {
		t.Fatal(err)
	}
}

type unsafeValue struct{}

func (unsafeValue) LogValue() slog.Value { panic("must not evaluate application code") }

func TestInvalidRecordsAndConfigNeverLeak(t *testing.T) {
	for _, c := range []obs.Config{{}, {Service: "x", Environment: "dev", Region: "r"}, {Service: "x", Environment: "prod", Region: "r", AllowedFields: []string{"trace_id"}}, {Service: "x", Environment: "prod", Region: "r", AllowedFields: []string{"x", "x"}}} {
		if _, err := obs.NewHandler(c, io.Discard); err == nil {
			t.Fatal("invalid config accepted")
		}
	}
	if _, err := obs.NewHandler(config(), nil); err == nil {
		t.Fatal("nil writer accepted")
	}
	var output bytes.Buffer
	h, _ := obs.NewHandler(config(), &output)
	cases := []slog.Record{
		slog.NewRecord(time.Date(3000, 1, 1, 0, 0, 0, 0, time.UTC), slog.LevelInfo, "invalid timestamp", 0), record(""), record(strings.Repeat("x", 1025)), record(string([]byte{0xff})),
		record("safe", slog.String("authorization", "private-sentinel")),
		record("safe", slog.String("trace_id", traceB)),
		record("safe", slog.String("event", "work.completed")),
		record("safe", slog.Float64("attempt", math.NaN())),
		record("safe", slog.Any("attempt", unsafeValue{})),
		record("safe", slog.Any("attempt", map[string]string{"secret": "private-sentinel"})),
		record("safe", slog.Int("attempt", 1), slog.Int("attempt", 2)),
		record("safe", slog.String("attempt", strings.Repeat("x", 1025))),
	}
	for _, r := range cases {
		if err := h.Handle(context.Background(), r); err == nil || strings.Contains(err.Error(), "sentinel") {
			t.Fatal("unsafe log accepted")
		}
	}
	if output.Len() != 0 || h.Stats().Invalid != uint64(len(cases)) {
		t.Fatal("invalid records leaked")
	}
	for _, handler := range []slog.Handler{h.WithAttrs([]slog.Attr{slog.String("service", "override")}), h.WithGroup(strings.Repeat("x", 129))} {
		if err := handler.Handle(context.Background(), record("invalid clone")); err == nil {
			t.Fatal("invalid clone accepted")
		}
	}
	if !h.Enabled(context.Background(), slog.Level(-8)) || h.Enabled(context.Background(), slog.Level(-9)) {
		t.Fatal("level filter")
	}
}

type blockingWriter struct {
	entered, release chan struct{}
	output           bytes.Buffer
}

func (w *blockingWriter) Write(b []byte) (int, error) {
	close(w.entered)
	<-w.release
	return w.output.Write(b)
}

type errorWriter struct {
	partial bool
	calls   int
}

func (w *errorWriter) Write(b []byte) (int, error) {
	w.calls++
	if w.partial {
		return len(b) / 2, nil
	}
	return 0, errors.New("private-sentinel")
}

func TestBackpressureCloseAndWriteFailures(t *testing.T) {
	w := &blockingWriter{entered: make(chan struct{}), release: make(chan struct{})}
	cfg := config()
	cfg.MaxWait = time.Millisecond
	h, _ := obs.NewHandler(cfg, w)
	done := make(chan error, 1)
	go func() { done <- h.Handle(context.Background(), record("first")) }()
	<-w.entered
	for range 100 {
		_ = h.WithGroup("").Handle(context.Background(), record("busy"))
	}
	if h.Stats().Busy != 100 {
		t.Fatal("unbounded sink wait")
	}
	h.Close()
	_ = h.Handle(context.Background(), record("closed"))
	close(w.release)
	if err := <-done; err != nil {
		t.Fatal(err)
	}
	if h.Stats().Written != 1 || h.Stats().Closed != 1 {
		t.Fatal(h.Stats())
	}
	for _, partial := range []bool{false, true} {
		w := &errorWriter{partial: partial}
		h, _ := obs.NewHandler(config(), w)
		for range 2 {
			err := h.Handle(context.Background(), record("safe"))
			if err == nil || strings.Contains(err.Error(), "sentinel") {
				t.Fatal("unsafe writer error")
			}
		}
		if h.Stats().IOErrors != 2 || partial && w.calls != 1 || !partial && w.calls != 2 {
			t.Fatal("incorrect recovery fence")
		}
	}
}

func BenchmarkHandler(b *testing.B) {
	h, _ := obs.NewHandler(config(), io.Discard)
	ctx := obs.IncomingContext(context.Background(), headers(parent), true)
	r := record("Work completed", slog.Int("attempt", 1))
	b.ReportAllocs()
	b.ResetTimer()
	for range b.N {
		_ = h.Handle(ctx, r)
	}
}

func TestConcurrentWritesAreCompleteLines(t *testing.T) {
	var output bytes.Buffer
	cfg := config()
	cfg.MaxWait = time.Second
	h, _ := obs.NewHandler(cfg, &output)
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
			if err := h.Handle(ctx, record("Concurrent", slog.Int("attempt", n))); err != nil {
				t.Error(err)
			}
		}(i)
	}
	for range 64 {
		<-ready
	}
	close(start)
	wg.Wait()
	if h.Stats().Written != 64 || h.Stats().Busy != 0 {
		t.Fatal(h.Stats())
	}
	for _, line := range bytes.Split(bytes.TrimSpace(output.Bytes()), []byte{'\n'}) {
		if got := contract.ValidateJSON(line, "correlated"); len(got) != 0 {
			t.Fatal(got)
		}
	}
}

func TestWaitingCapacityAndCloseWakeup(t *testing.T) {
	w := &blockingWriter{entered: make(chan struct{}), release: make(chan struct{})}
	cfg := config()
	cfg.MaxWait = time.Second
	h, _ := obs.NewHandler(cfg, w)
	var wg sync.WaitGroup
	wg.Add(1)
	go func() { defer wg.Done(); _ = h.Handle(context.Background(), record("entered")) }()
	<-w.entered
	// Cleanup always releases the injected stalled sink, even if an assertion fails.
	defer func() { h.Close(); close(w.release); wg.Wait() }()
	for range 127 {
		wg.Add(1)
		go func() { defer wg.Done(); _ = h.Handle(context.Background(), record("waiting")) }()
	}
	deadline := time.Now().Add(750 * time.Millisecond)
	for h.Stats().Pending != 128 {
		if time.Now().After(deadline) {
			t.Fatal("waiters did not reach capacity", h.Stats())
		}
		runtime.Gosched()
	}
	_ = h.Handle(context.Background(), record("over capacity"))
	if h.Stats().Busy != 1 || h.Stats().Pending != 128 {
		t.Fatal(h.Stats())
	}
	h.Close()
	deadline = time.Now().Add(750 * time.Millisecond)
	for h.Stats().Pending != 1 {
		if time.Now().After(deadline) {
			t.Fatal("close did not wake waiters", h.Stats())
		}
		runtime.Gosched()
	}
	if h.Stats().Closed != 127 {
		t.Fatal(h.Stats())
	}
}

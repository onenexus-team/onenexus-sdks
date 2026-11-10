package observability_test

// The shared write model (tests/logging/scenarios.json write_model, design
// review F2): the caller never waits on the output; a bounded queue feeds one
// background writer; a full queue drops and counts (Busy = queue_full); a write
// error is counted and the writer continues; close drains until a deadline.

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"reflect"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	obs "github.com/onenexus-team/onenexus-sdks/go/packages/observability"
)

type writeModel struct {
	QueueCapacity  int      `json:"queue_capacity"`
	CloseTimeoutMS int      `json:"close_timeout_ms"`
	CallerBudgetMS int      `json:"caller_budget_ms"`
	ErrorWaitMS    int      `json:"error_wait_ms"`
	Counters       []string `json:"counters"`
	Cases          []struct {
		ID        string   `json:"id"`
		Lines     int      `json:"lines"`
		Languages []string `json:"languages"`
	} `json:"cases"`
}

func loadWriteModel(t *testing.T) writeModel {
	t.Helper()
	path := os.Getenv("ONENEXUS_LOGGING_SCENARIOS")
	if path == "" {
		path = "../../../../tests/logging/scenarios.json"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var suite struct {
		Model writeModel `json:"write_model"`
	}
	if err = json.Unmarshal(data, &suite); err != nil {
		t.Fatal(err)
	}
	return suite.Model
}

func (m writeModel) lines(t *testing.T, id string) int {
	t.Helper()
	for _, c := range m.Cases {
		if c.ID == id {
			return c.Lines
		}
	}
	t.Fatal("missing write_model case", id)
	return 0
}

// syncOutput is a goroutine-safe test output. Reads first wait until the
// handler's queue is drained, because the handler writes in the background.
type syncOutput struct {
	mu  sync.Mutex
	buf bytes.Buffer
	h   *obs.Handler
}

func newSyncHandler(t *testing.T, cfg obs.Config) (*obs.Handler, *syncOutput) {
	t.Helper()
	out := &syncOutput{}
	h, err := obs.NewHandler(cfg, out)
	if err != nil {
		t.Fatal(err)
	}
	out.h = h
	return h, out
}

func (o *syncOutput) Write(b []byte) (int, error) {
	o.mu.Lock()
	defer o.mu.Unlock()
	return o.buf.Write(b)
}

func (o *syncOutput) drain() {
	if o.h == nil {
		return
	}
	deadline := time.Now().Add(obs.CloseTimeout)
	for o.h.Stats().Pending != 0 && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
}

func (o *syncOutput) Bytes() []byte {
	o.drain()
	o.mu.Lock()
	defer o.mu.Unlock()
	return bytes.Clone(o.buf.Bytes())
}

func (o *syncOutput) String() string { return string(o.Bytes()) }
func (o *syncOutput) Len() int       { return len(o.Bytes()) }
func (o *syncOutput) Reset() {
	o.drain()
	o.mu.Lock()
	defer o.mu.Unlock()
	o.buf.Reset()
}

// gateWriter blocks every Write until open is closed (a blocked stdout pipe).
type gateWriter struct {
	syncOutput
	entered chan struct{}
	once    sync.Once
	open    chan struct{}
}

func newGate() *gateWriter {
	return &gateWriter{entered: make(chan struct{}), open: make(chan struct{})}
}

func (w *gateWriter) Write(b []byte) (int, error) {
	w.once.Do(func() { close(w.entered) })
	<-w.open
	return w.syncOutput.Write(b)
}

// firstWriter runs fail on the first Write only.
type firstWriter struct {
	syncOutput
	calls int // only the handler's writer goroutine touches it
	fail  func(w *firstWriter, b []byte) (int, error)
}

func (w *firstWriter) Write(b []byte) (int, error) {
	w.calls++
	if w.calls == 1 {
		return w.fail(w, b)
	}
	return w.syncOutput.Write(b)
}

type slowWriter struct{ syncOutput }

func (w *slowWriter) Write(b []byte) (int, error) {
	time.Sleep(10 * time.Millisecond)
	return w.syncOutput.Write(b)
}

func emit(t *testing.T, h *obs.Handler, n int) {
	t.Helper()
	logger := slog.New(h)
	for i := range n {
		logger.Info(fmt.Sprintf("line %d", i))
	}
}

func messages(t *testing.T, text []byte) []string {
	t.Helper()
	var got []string
	for _, line := range bytes.Split(bytes.TrimSuffix(text, []byte{'\n'}), []byte{'\n'}) {
		var row map[string]any
		if err := json.Unmarshal(line, &row); err != nil {
			t.Fatalf("invalid JSON line %q", line)
		}
		got = append(got, row["message"].(string))
	}
	return got
}

func TestWriteModelConstantsMatchSharedModel(t *testing.T) {
	m := loadWriteModel(t)
	if obs.QueueCapacity != m.QueueCapacity || obs.CloseTimeout != time.Duration(m.CloseTimeoutMS)*time.Millisecond || obs.ErrorWait != time.Duration(m.ErrorWaitMS)*time.Millisecond {
		t.Fatal("constants differ from scenarios.json", m.QueueCapacity, m.CloseTimeoutMS)
	}
	// Busy is the shared queue_full counter.
	fields := map[string]string{"written": "Written", "invalid": "Invalid", "queue_full": "Busy", "io_errors": "IOErrors", "closed": "Closed", "pending": "Pending"}
	stats := reflect.TypeFor[obs.Stats]()
	if len(m.Counters) != len(fields) || stats.NumField() != len(fields) {
		t.Fatal("counter set differs", m.Counters)
	}
	for _, name := range m.Counters {
		if _, ok := stats.FieldByName(fields[name]); !ok {
			t.Fatal("missing counter", name)
		}
	}
	for _, c := range m.Cases {
		if slicesContains(c.Languages, "go") && c.Lines < 0 {
			t.Fatal("bad case", c.ID)
		}
	}
}

func slicesContains(list []string, want string) bool {
	for _, v := range list {
		if v == want {
			return true
		}
	}
	return false
}

// blocked_output_never_blocks_caller
func TestBlockedOutputNeverBlocksCaller(t *testing.T) {
	m := loadWriteModel(t)
	total := m.lines(t, "blocked_output_never_blocks_caller")
	w := newGate()
	h, err := obs.NewHandler(config(), w)
	if err != nil {
		t.Fatal(err)
	}
	released := false
	defer func() {
		if !released {
			close(w.open)
		}
	}()
	logger := slog.New(h)
	var slowest time.Duration
	for i := range total {
		start := time.Now()
		logger.Info(fmt.Sprintf("line %d", i))
		slowest = max(slowest, time.Since(start))
	}
	budget := time.Duration(m.CallerBudgetMS) * time.Millisecond
	s := h.Stats()
	if slowest >= budget {
		t.Fatal("caller waited on the output", slowest)
	}
	if int(s.Busy) < total-m.QueueCapacity-1 || s.Written != 0 {
		t.Fatal("queue not bounded", s)
	}
	close(w.open) // the output recovers: queued lines are written
	released = true
	if !h.CloseWithin(obs.CloseTimeout) {
		t.Fatal("queued lines lost", h.Stats())
	}
	s = h.Stats()
	if s.Written != uint64(total)-s.Busy || s.Pending != 0 || s.IOErrors != 0 {
		t.Fatal(s)
	}
	if got := messages(t, w.buf.Bytes()); len(got) != int(s.Written) || got[0] != "line 0" {
		t.Fatal("queued lines not written in order", len(got))
	}
}

// write_error_recovers
func TestWriteErrorRecovers(t *testing.T) {
	m := loadWriteModel(t)
	w := &firstWriter{fail: func(*firstWriter, []byte) (int, error) { return 0, errors.New("private-sentinel") }}
	h, _ := obs.NewHandler(config(), w)
	emit(t, h, m.lines(t, "write_error_recovers"))
	if !h.CloseWithin(obs.CloseTimeout) {
		t.Fatal("not drained")
	}
	if s := h.Stats(); s.IOErrors != 1 || s.Written != 2 || s.Pending != 0 {
		t.Fatal(s)
	}
	if got := messages(t, w.buf.Bytes()); !reflect.DeepEqual(got, []string{"line 1", "line 2"}) {
		t.Fatal("later lines not written", got)
	}
}

// partial_write_recovers: a failed write that wrote part of a line (with an
// error, or a short write with a nil error) is counted, and the next line starts
// on a new line, so every complete line is valid JSON.
func TestPartialWriteRecovers(t *testing.T) {
	m := loadWriteModel(t)
	for name, result := range map[string]error{"error": errors.New("private-sentinel"), "short": nil} {
		t.Run(name, func(t *testing.T) {
			w := &firstWriter{fail: func(w *firstWriter, b []byte) (int, error) {
				n, _ := w.syncOutput.Write(b[:len(b)/2])
				return n, result
			}}
			h, _ := obs.NewHandler(config(), w)
			emit(t, h, m.lines(t, "partial_write_recovers"))
			if !h.CloseWithin(obs.CloseTimeout) {
				t.Fatal("not drained")
			}
			if s := h.Stats(); s.IOErrors != 1 || s.Written != 1 {
				t.Fatal(s)
			}
			parts := bytes.Split(w.buf.Bytes(), []byte{'\n'})
			if len(parts) != 3 || len(parts[2]) != 0 || json.Valid(parts[0]) {
				t.Fatalf("cut line not ended: %q", w.buf.Bytes())
			}
			if got := messages(t, parts[1]); !reflect.DeepEqual(got, []string{"line 1"}) {
				t.Fatal(got)
			}
		})
	}
}

func TestPanickingWriterIsCountedNotFatal(t *testing.T) {
	w := &firstWriter{fail: func(*firstWriter, []byte) (int, error) { panic("private-sentinel") }}
	h, _ := obs.NewHandler(config(), w)
	emit(t, h, 2)
	if !h.CloseWithin(obs.CloseTimeout) {
		t.Fatal("not drained")
	}
	if s := h.Stats(); s.IOErrors != 1 || s.Written != 1 {
		t.Fatal(s)
	}
	// The outcome of a panic is unknown, so the next line starts on a new line.
	if !bytes.HasPrefix(w.buf.Bytes(), []byte{'\n'}) || messages(t, bytes.TrimPrefix(w.buf.Bytes(), []byte{'\n'}))[0] != "line 1" {
		t.Fatalf("%q", w.buf.Bytes())
	}
}

// close_drains
func TestCloseDrains(t *testing.T) {
	m := loadWriteModel(t)
	total := m.lines(t, "close_drains")
	w := &slowWriter{}
	h, _ := obs.NewHandler(config(), w)
	emit(t, h, total)
	if !h.CloseWithin(obs.CloseTimeout) {
		t.Fatal("close reported loss", h.Stats())
	}
	if s := h.Stats(); s.Written != uint64(total) || s.Pending != 0 {
		t.Fatal(s)
	}
	if got := messages(t, w.buf.Bytes()); len(got) != total {
		t.Fatal(got)
	}
	h.Close() // a second Close is harmless
}

// close_deadline: Close (default CloseTimeout) on a blocked output returns
// failure within close_timeout_ms + 500 ms and counts the undelivered lines.
func TestCloseDeadline(t *testing.T) {
	m := loadWriteModel(t)
	total := m.lines(t, "close_deadline")
	w := newGate()
	defer close(w.open)
	h, _ := obs.NewHandler(config(), w)
	emit(t, h, total)
	<-w.entered
	start := time.Now()
	h.Close()
	if elapsed := time.Since(start); elapsed > time.Duration(m.CloseTimeoutMS+500)*time.Millisecond || elapsed < obs.CloseTimeout {
		t.Fatal("close did not wait for the deadline", elapsed)
	}
	if s := h.Stats(); s.Pending != total || s.Written != 0 {
		t.Fatal("undelivered lines not counted", s)
	}
	if h.CloseWithin(0) {
		t.Fatal("second close reported success with lines lost")
	}
}

func TestCloseWithinBlockedWriterReturnsFalse(t *testing.T) {
	w := newGate()
	h, _ := obs.NewHandler(config(), w)
	emit(t, h, 3)
	<-w.entered
	timeout := 100 * time.Millisecond
	start := time.Now()
	if h.CloseWithin(timeout) {
		t.Fatal("blocked writer reported drained")
	}
	if elapsed := time.Since(start); elapsed > timeout+500*time.Millisecond {
		t.Fatal("close exceeded its deadline", elapsed)
	}
	if s := h.Stats(); s.Pending != 3 {
		t.Fatal(s)
	}
	close(w.open) // the blocked Write finishes; the stopped writer writes nothing more
	deadline := time.Now().Add(time.Second)
	for h.Stats().Written != 1 && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	time.Sleep(20 * time.Millisecond)
	if s := h.Stats(); s.Written != 1 || s.Pending != 2 {
		t.Fatal(s)
	}
}

// log_after_close
func TestLogAfterClose(t *testing.T) {
	m := loadWriteModel(t)
	h, out := newSyncHandler(t, config())
	child := h.WithAttrs([]slog.Attr{slog.Int("attempt", 1)})
	if !h.CloseWithin(obs.CloseTimeout) || !h.CloseWithin(obs.CloseTimeout) {
		t.Fatal("empty close reported loss")
	}
	for range m.lines(t, "log_after_close") {
		if err := child.Handle(context.Background(), record("after close")); err != nil {
			t.Fatal(err)
		}
	}
	if s := h.Stats(); s.Closed != 1 || s.Written != 0 || s.Pending != 0 || out.Len() != 0 {
		t.Fatal(s)
	}
}

func TestConcurrentHandleSharesOneWriter(t *testing.T) {
	h, out := newSyncHandler(t, config())
	const workers, each = 16, 64 // within QueueCapacity, so nothing is dropped
	var wg sync.WaitGroup
	start := make(chan struct{})
	for g := range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			logger := slog.New(h).With("attempt", g)
			<-start
			for i := range each {
				logger.Info(fmt.Sprintf("worker %d line %d", g, i))
				if i%16 == 0 {
					runtime.Gosched()
					_ = h.Stats()
				}
			}
		}()
	}
	close(start)
	wg.Wait()
	if !h.CloseWithin(obs.CloseTimeout) {
		t.Fatal("not drained")
	}
	if s := h.Stats(); s.Written != workers*each || s.Busy != 0 || s.IOErrors != 0 {
		t.Fatal(s)
	}
	lines := bytes.Split(bytes.TrimSpace(out.Bytes()), []byte{'\n'})
	if len(lines) != workers*each {
		t.Fatal(len(lines))
	}
	for _, line := range lines {
		if got := obs.ValidateJSON(line, "common"); len(got) != 0 {
			t.Fatal(got)
		}
	}
}

const hardExitChild = "ONENEXUS_WRITE_MODEL_HARD_EXIT_CHILD"

// error_line_survives_hard_exit: a child process logs one ERROR line through a
// slow stdout (20 ms per write) and calls os.Exit(1) without Close; the line
// must be on its output.
func TestErrorLineSurvivesHardExit(t *testing.T) {
	if os.Getenv(hardExitChild) == "1" {
		h, err := obs.NewHandler(config(), slowStdout{})
		if err != nil {
			os.Exit(3)
		}
		slog.New(h).Error("Fatal before exit", "attempt", 1)
		os.Exit(1)
	}
	cmd := exec.Command(os.Args[0], "-test.run=^TestErrorLineSurvivesHardExit$", "-test.count=1")
	cmd.Env = append(os.Environ(), hardExitChild+"=1")
	out, err := cmd.Output()
	var exit *exec.ExitError
	if !errors.As(err, &exit) || exit.ExitCode() != 1 {
		t.Fatal("child did not exit hard", err)
	}
	found := false
	for _, line := range strings.Split(string(out), "\n") {
		var row map[string]any
		if json.Unmarshal([]byte(line), &row) == nil && row["message"] == "Fatal before exit" && row["level"] == "ERROR" {
			found = true
		}
	}
	if !found {
		t.Fatalf("ERROR line lost at hard exit: %q", out)
	}
}

type slowStdout struct{}

func (slowStdout) Write(b []byte) (int, error) {
	time.Sleep(20 * time.Millisecond)
	return os.Stdout.Write(b)
}

// error_line_survives_hard_exit: the ERROR wait is bounded on a blocked output,
// and non-error lines never wait.
func TestErrorWaitIsBounded(t *testing.T) {
	m := loadWriteModel(t)
	w := newGate()
	defer close(w.open)
	h, _ := obs.NewHandler(config(), w)
	logger := slog.New(h)
	start := time.Now()
	logger.Info("not waiting")
	if elapsed := time.Since(start); elapsed >= obs.ErrorWait {
		t.Fatal("INFO waited", elapsed)
	}
	<-w.entered
	start = time.Now()
	logger.Error("bounded")
	if elapsed := time.Since(start); elapsed > time.Duration(m.ErrorWaitMS+50)*time.Millisecond {
		t.Fatal("ERROR wait not bounded", elapsed)
	}
	if s := h.Stats(); s.Pending != 2 {
		t.Fatal(s)
	}
}

// selfLogger logs an ERROR through its own handler from inside Write, as a
// writer that reports its own failure would: the writer goroutine never waits.
type selfLogger struct {
	syncOutput
	logger *slog.Logger
	calls  int
	waited time.Duration
}

func (w *selfLogger) Write(b []byte) (int, error) {
	w.calls++
	if w.calls == 1 {
		start := time.Now()
		w.logger.Error("from the writer")
		w.waited = time.Since(start)
	}
	return w.syncOutput.Write(b)
}

func TestErrorFromWriterGoroutineDoesNotWait(t *testing.T) {
	w := &selfLogger{}
	h, _ := obs.NewHandler(config(), w)
	w.logger = slog.New(h)
	w.logger.Info("first")
	deadline := time.Now().Add(time.Second)
	for h.Stats().Written != 2 && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	if !h.CloseWithin(obs.CloseTimeout) {
		t.Fatal("not drained")
	}
	if got := messages(t, w.buf.Bytes()); !reflect.DeepEqual(got, []string{"first", "from the writer"}) {
		t.Fatal(got)
	}
	if w.waited >= obs.ErrorWait {
		t.Fatal("writer goroutine waited on itself", w.waited)
	}
}

func waitGoroutines(want int) int {
	deadline := time.Now().Add(2 * time.Second)
	n := runtime.NumGoroutine()
	for n != want && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
		n = runtime.NumGoroutine()
	}
	return n
}

// unused_logger_owns_no_writer: creating handlers starts no goroutine; the first
// accepted line starts one writer; Close stops it.
func TestUnusedLoggerOwnsNoWriter(t *testing.T) {
	base := waitGoroutines(runtime.NumGoroutine())
	handlers := make([]*obs.Handler, 50)
	for i := range handlers {
		handlers[i], _ = obs.NewHandler(config(), &syncOutput{})
		_ = handlers[i].WithGroup("job").WithAttrs([]slog.Attr{slog.Int("attempt", 1)})
	}
	if n := waitGoroutines(base); n != base {
		t.Fatal("unused handlers started goroutines", n-base)
	}
	slog.New(handlers[0]).Info("first line")
	if n := waitGoroutines(base + 1); n != base+1 {
		t.Fatal("first line did not start exactly one writer", n-base)
	}
	for _, h := range handlers {
		if !h.CloseWithin(obs.CloseTimeout) {
			t.Fatal("not drained")
		}
	}
	if n := waitGoroutines(base); n != base {
		t.Fatal("writer kept after Close", n-base)
	}
}

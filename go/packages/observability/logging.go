package observability

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"math"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
	"unicode"
	"unicode/utf8"
)

type Config struct {
	Service, Environment, Region string
	// AllowedFields names the custom fields this service may log (full dotted
	// names, also under WithGroup). Each must pass CheckAllowedFields.
	AllowedFields []string
	MinLevel      slog.Level
	// Deprecated: MaxWait is ignored. The caller never waits on the writer
	// (tests/logging write_model). Values 0..1s are still accepted so existing
	// callers keep compiling and validating.
	MaxWait time.Duration
}

// The shared write model (tests/logging/scenarios.json write_model).
const (
	// QueueCapacity is the number of accepted lines that may wait for the writer.
	QueueCapacity = 1024
	// CloseTimeout is how long Close drains queued lines.
	CloseTimeout = 2 * time.Second
	// ErrorWait is how long an ERROR or FATAL call waits for its own line to be
	// written, so the line survives an os.Exit or log.Fatal right after it.
	ErrorWait = 50 * time.Millisecond
)

// Stats are the shared write-model counters. Busy is the shared "queue_full"
// counter: a line dropped because QueueCapacity lines were already waiting.
// Pending counts lines accepted but not yet written.
type Stats struct {
	Written, Invalid, Busy, IOErrors, Closed uint64
	Pending                                  int
}
type counters struct{ written, invalid, busy, ioErrors, closed atomic.Uint64 }

// queued is one line; done, when set, is closed once the line was handled.
type queued struct {
	line []byte
	done chan struct{}
}

// sink is one bounded queue and the one goroutine that owns every write to the
// caller's writer. Logger clones share it.
type sink struct {
	mu       sync.RWMutex // senders hold it shared; Close holds it to close queue
	closed   atomic.Bool
	started  atomic.Bool // the writer goroutine starts with the first accepted line
	start    sync.Once
	writerID atomic.Uint64 // goroutine id of the writer, set when it starts
	queue    chan queued
	exited   chan struct{} // closed when the writer goroutine returns
	stop     chan struct{} // closed when a Close deadline passed
	once     sync.Once
	stopOnce sync.Once
	pending  atomic.Int64
	writer   io.Writer
	// midLine is owned by the writer goroutine: a failed write left part of a
	// line on the output, so the next line must start with "\n".
	midLine  bool
	counters counters
	drops    *serviceDrops // this service's process-wide drop metric (R1)
}

// Handler is an opt-in slog handler. Clones share one sink and its counters.
// Handle builds and validates the line on the caller goroutine, then hands it to
// a bounded queue (QueueCapacity lines) read by one background goroutine; the
// caller never waits on the writer. A full queue drops the line (Busy), a write
// error is counted (IOErrors) and the next line is still written. Call Close at
// shutdown to drain queued lines: the goroutine starts with the first accepted
// line and runs until Close. An ERROR or FATAL call waits up to ErrorWait for
// its own line, so it survives os.Exit. The caller still owns the writer.
type Handler struct {
	config                    Config
	allowed                   map[string]bool
	sink                      *sink
	attrs                     map[string]any
	group                     string
	badGroup                  bool
	state                     fieldState
	messageLimit, recordLimit int
	fieldLimit, stackLimit    int
	errorTypeLimit, maxDrops  int
}

// fieldState records what was shortened, removed or recognised as an error.
type fieldState struct {
	dropped   int
	truncated bool
	errorType string
}

func (f *fieldState) merge(later fieldState) {
	f.dropped += later.dropped
	f.truncated = f.truncated || later.truncated
	if later.errorType != "" {
		f.errorType = later.errorType
	}
}

const (
	errorTypeField   = "error.type"
	stacktraceField  = "exception.stacktrace"
	truncatedField   = "logging.truncated"
	droppedField     = "logging.dropped_field_count"
	fingerprintField = "logging.error_fingerprint"
	truncationMark   = "\u2026"
)

// packagePrefix identifies this package's frames, which call-site stacks skip.
var packagePrefix = func() string {
	pc, _, _, _ := runtime.Caller(0)
	name := runtime.FuncForPC(pc).Name()
	slash := strings.LastIndexByte(name, '/') + 1
	return name[:slash+strings.IndexByte(name[slash:], '.')+1]
}()

var fieldName = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9._-]{0,127}$`)
var errInvalid = errors.New("invalid_log_record")
var errIO = errors.New("log_write_failed")

// NewHandler validates configuration before serving work. It never changes slog's
// global default and never closes the caller-owned writer.
func NewHandler(config Config, writer io.Writer) (*Handler, error) {
	if writer == nil || config.MaxWait < 0 || config.MaxWait > time.Second {
		return nil, errors.New("invalid_log_config")
	}
	b, err := Load()
	if err != nil {
		return nil, err
	}
	if err = CheckAllowedFields(config.AllowedFields); err != nil {
		return nil, err
	}
	h := &Handler{config: config, allowed: make(map[string]bool), attrs: make(map[string]any), messageLimit: b.MaxMessageBytes, recordLimit: b.MaxRecordBytes, fieldLimit: b.MaxFieldBytes, stackLimit: b.MaxStacktraceBytes, errorTypeLimit: b.MaxErrorTypeChars, maxDrops: b.MaxDroppedFieldCount}
	h.config.AllowedFields = nil
	for _, field := range config.AllowedFields {
		h.allowed[field] = true
	}
	data, _ := json.Marshal(map[string]any{"timestamp": 0, "level": "INFO", "message": "Startup validation", "service": config.Service, "region": config.Region, "environment": config.Environment})
	for _, field := range requestFieldNames {
		h.allowed[field] = true
	}
	if !utf8.ValidString(config.Service+config.Region+config.Environment) || len(ValidateJSON(data, "common")) > 0 {
		return nil, errors.New("invalid_log_config")
	}
	h.sink = &sink{writer: writer, drops: registerDrops(config.Service), exited: make(chan struct{}), stop: make(chan struct{})}
	return h, nil
}

func (h *Handler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.config.MinLevel
}

func levelName(level slog.Level) string {
	switch {
	case level < slog.LevelDebug:
		return "TRACE"
	case level < slog.LevelInfo:
		return "DEBUG"
	case level < slog.LevelWarn:
		return "INFO"
	case level < slog.LevelError:
		return "WARN"
	case level < slog.LevelError+4:
		return "ERROR"
	default:
		return "FATAL"
	}
}

// Handle keeps the line: a long message or string is shortened, a field that
// cannot be emitted is removed and counted, and an error attr adds its type and
// call-site frames. Only a record that still breaks the contract is dropped; it
// returns only stable errors and never echoes values. slog ignores handler errors.
// Every line not written is also counted on the drop metric (DropCounts).
func (h *Handler) Handle(ctx context.Context, record slog.Record) error {
	s := h.sink
	if s.closed.Load() {
		s.drop(&s.counters.closed, reasonClosed)
		return nil
	}
	if !utf8.ValidString(record.Message) {
		s.drop(&s.counters.invalid, reasonInvalid)
		return errInvalid
	}
	message, cut := shorten(record.Message, h.messageLimit)
	attrs := make(map[string]any, len(h.attrs)+min(record.NumAttrs(), 34))
	for k, v := range h.attrs {
		attrs[k] = v
	}
	state := h.state
	var own fieldState
	own.truncated = cut
	record.Attrs(func(a slog.Attr) bool { h.add(attrs, &own, h.group, a, 0); return true })
	state.merge(own)
	// Only caller attributes may be removed to fit; base and request fields stay.
	removable := make([]string, 0, len(attrs))
	for k := range attrs {
		if k != "event" && k != "outcome" && !slices.Contains(requestFieldNames, k) {
			removable = append(removable, k)
		}
	}
	for k, v := range CurrentRequestFields(ctx) {
		attrs[k] = v
	}
	_, hasEvent := attrs["event"]
	_, hasOutcome := attrs["outcome"]
	if hasEvent != hasOutcome {
		s.drop(&s.counters.invalid, reasonInvalid)
		return errInvalid
	}
	if state.errorType != "" {
		// A caller-supplied value wins.
		if _, ok := attrs[errorTypeField]; !ok {
			attrs[errorTypeField] = state.errorType
		}
		if _, ok := attrs[stacktraceField]; !ok {
			if stack, cut := callStack(h.stackLimit); stack != "" {
				attrs[stacktraceField] = stack
				state.truncated = state.truncated || cut
			}
		}
	}
	t := record.Time
	if t.IsZero() {
		t = time.Now()
	}
	if !time.Unix(0, t.UnixNano()).Equal(t) {
		s.drop(&s.counters.invalid, reasonInvalid)
		return errInvalid
	}
	attrs["timestamp"] = t.UnixNano()
	attrs["level"] = levelName(record.Level)
	attrs["message"] = message
	attrs["service"] = h.config.Service
	attrs["environment"] = h.config.Environment
	attrs["region"] = h.config.Region
	profile := "common"
	if id := TraceID(ctx); id != "" {
		attrs["trace_id"] = id
		profile = "correlated"
		if hasEvent {
			profile = "lifecycle"
		}
	}
	if _, ok := attrs["request_event"]; ok {
		profile = "request"
	}
	if errorType, ok := attrs[errorTypeField].(string); ok {
		// Before fitting: a shortened stack keeps the fingerprint.
		stack, _ := attrs[stacktraceField].(string)
		attrs[fingerprintField] = ErrorFingerprint(errorType, stack)
	}
	buf, err := h.fit(attrs, removable, state)
	if err != nil || buf.Len()-1 > h.recordLimit || len(ValidateJSON(buf.Bytes(), profile)) > 0 {
		s.drop(&s.counters.invalid, reasonInvalid)
		return errInvalid
	}
	// An ERROR/FATAL line waits (bounded) until it is written, so it survives a
	// hard exit that follows; never on the writer goroutine (a writer that logs).
	var done chan struct{}
	if record.Level >= slog.LevelError && (!s.started.Load() || goroutineID() != s.writerID.Load()) {
		done = make(chan struct{})
	}
	if s.submit(queued{buf.Bytes(), done}) && done != nil {
		timer := time.NewTimer(ErrorWait)
		defer timer.Stop()
		select {
		case <-done:
		case <-timer.C:
		}
	}
	return nil
}

// submit queues a line without waiting and reports whether it was accepted.
// Under the shared lock no line can be queued after Close closed the queue.
// The queue and its goroutine are created with the first accepted line, so a
// handler that never logs owns no goroutine.
func (s *sink) submit(item queued) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.closed.Load() {
		s.drop(&s.counters.closed, reasonClosed)
		return false
	}
	s.start.Do(func() {
		s.queue = make(chan queued, QueueCapacity)
		ready := make(chan struct{})
		go s.run(ready)
		<-ready
		s.started.Store(true)
	})
	s.pending.Add(1)
	select {
	case s.queue <- item:
		return true
	default:
		s.pending.Add(-1)
		s.drop(&s.counters.busy, reasonQueueFull)
		return false
	}
}

// drop counts one line not written: on this handler's Stats and on the
// service's process-wide drop metric.
func (s *sink) drop(local *atomic.Uint64, reason reasonIndex) {
	local.Add(1)
	s.drops[reason].Add(1)
}

// goroutineID parses the current goroutine's id ("goroutine 7 [running]:").
func goroutineID() uint64 {
	var buf [32]byte
	b := buf[:runtime.Stack(buf[:], false)]
	b = bytes.TrimPrefix(b, []byte("goroutine "))
	id, _ := strconv.ParseUint(string(b[:max(bytes.IndexByte(b, ' '), 0)]), 10, 64)
	return id
}

// run is the one goroutine that writes. It ends when Close closed the queue and
// every line is written, or when a Close deadline passed (lines left stay Pending).
func (s *sink) run(ready chan<- struct{}) {
	defer close(s.exited)
	s.writerID.Store(goroutineID())
	close(ready)
	for item := range s.queue {
		select {
		case <-s.stop:
			return
		default:
		}
		s.write(item.line)
		s.pending.Add(-1)
		if item.done != nil {
			close(item.done)
		}
	}
}

// write writes one line; it never retries. A failed or short write is counted
// and the writer goes on. When the failure left part of a line on the output,
// the next line is preceded by "\n" so it starts on its own line.
func (s *sink) write(line []byte) {
	data, prefixed := line, s.midLine
	if prefixed {
		data = append(append(make([]byte, 0, len(line)+1), '\n'), line...)
	}
	n, err := s.safeWrite(data)
	if err == nil && n != len(data) {
		err = io.ErrShortWrite
	}
	if err == nil {
		s.midLine = false
		s.counters.written.Add(1)
		return
	}
	s.drop(&s.counters.ioErrors, reasonIOErrors)
	switch {
	case n < 0 || n > len(data):
		s.midLine = true // unknown (a panic or a writer breaking the io.Writer contract)
	case prefixed:
		s.midLine = n != 1 // 0: still mid-line; >1: part of this line was written
	default:
		s.midLine = n > 0
	}
}

// safeWrite turns a panicking writer into a counted error instead of a crash.
func (s *sink) safeWrite(data []byte) (n int, err error) {
	defer func() {
		if recover() != nil {
			n, err = -1, errIO
		}
	}()
	return s.writer.Write(data)
}

// add copies one attribute. A value that cannot be emitted (an object, such as
// a named group, an array or a registered field of another type) is removed and
// counted; an error value is reported through error.type instead.
func (h *Handler) add(dst map[string]any, state *fieldState, prefix string, attr slog.Attr, depth int) {
	if attr.Equal(slog.Attr{}) {
		return
	}
	if kind := attr.Value.Kind(); kind == slog.KindAny || kind == slog.KindLogValuer {
		if err, ok := attr.Value.Any().(error); ok {
			if state.errorType == "" {
				state.errorType = errorType(err, h.errorTypeLimit)
			}
			return
		}
	}
	if depth > 8 || (depth == 0 && h.badGroup) || len(attr.Key) > 128 || !utf8.ValidString(attr.Key) {
		state.dropped++
		return
	}
	// slog inlines a group without a key; a named group is an object value.
	if attr.Value.Kind() == slog.KindGroup && attr.Key == "" {
		for _, a := range attr.Value.Group() {
			h.add(dst, state, prefix, a, depth+1)
		}
		return
	}
	key := prefix + attr.Key
	if _, ok := dst[key]; ok || len(dst) >= 34 || (!h.allowed[key] && key != "event" && key != "outcome") || !registry.accepts(key, attr.Value) {
		state.dropped++
		return
	}
	var value any
	switch attr.Value.Kind() {
	case slog.KindString:
		text := attr.Value.String()
		if !utf8.ValidString(text) || !h.validErrorField(key, text) {
			state.dropped++
			return
		}
		limit := h.fieldLimit
		if key == stacktraceField {
			limit = h.stackLimit
		}
		var cut bool
		value, cut = shorten(text, limit)
		state.truncated = state.truncated || cut
	case slog.KindBool:
		value = attr.Value.Bool()
	case slog.KindInt64:
		value = attr.Value.Int64()
	case slog.KindUint64:
		value = attr.Value.Uint64()
	case slog.KindFloat64:
		value = attr.Value.Float64()
		if math.IsNaN(value.(float64)) || math.IsInf(value.(float64), 0) {
			state.dropped++
			return
		}
	case slog.KindAny:
		if attr.Value.Any() != nil {
			state.dropped++
			return
		}
	default:
		state.dropped++ // Never call user LogValuer, Stringer or JSON methods.
		return
	}
	dst[key] = value
}

// shorten cuts at a rune boundary so the text plus the mark fits limit bytes.
func shorten(text string, limit int) (string, bool) {
	if len(text) <= limit {
		return text, false
	}
	i := max(limit-len(truncationMark), 0)
	for i > 0 && !utf8.RuneStart(text[i]) {
		i--
	}
	return text[:i] + truncationMark, true
}

// errorType names the dynamic type only; it never calls the error's methods.
func errorType(err error, limit int) string {
	name := fmt.Sprintf("%T", err)
	if strings.IndexFunc(name, unicode.IsSpace) >= 0 {
		name = strings.Join(strings.Fields(name), "")
	}
	if runes := []rune(name); len(runes) > limit {
		name = string(runes[:limit])
	}
	return name
}

// validErrorField applies the schema rule of a caller-supplied error field, so
// a bad value is removed at intake and the SDK value can apply instead.
func (h *Handler) validErrorField(key, text string) bool {
	switch key {
	case errorTypeField:
		return text != "" && utf8.RuneCountInString(text) <= h.errorTypeLimit && strings.IndexFunc(text, unicode.IsSpace) < 0
	case stacktraceField:
		return text != ""
	}
	return true
}

var frameLine = regexp.MustCompile(`:[0-9]+\)$`)

// ErrorFingerprint groups one failure across lines and builds
// (tests/logging error_fingerprint): the type and each frame without its line
// number; never the message. An empty stacktrace means no frames.
func ErrorFingerprint(errorType, stacktrace string) string {
	var b strings.Builder
	b.WriteString(errorType)
	if stacktrace != "" {
		for _, frame := range strings.Split(stacktrace, "\n") {
			b.WriteByte('\n')
			b.WriteString(frameLine.ReplaceAllString(frame, ")"))
		}
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])[:16]
}

// callStack formats the logging call site, innermost first, as whole frames
// within limit bytes. Inside a deferred recover it includes the panicking frames.
func callStack(limit int) (string, bool) {
	pcs := make([]uintptr, 64)
	n := runtime.Callers(2, pcs)
	frames := runtime.CallersFrames(pcs[:n])
	var b strings.Builder
	for more := n > 0; more; {
		var frame runtime.Frame
		frame, more = frames.Next()
		if frame.Function == "" || strings.HasPrefix(frame.Function, packagePrefix) || strings.HasPrefix(frame.Function, "log/slog.") {
			continue
		}
		line := "at " + frame.Function
		if frame.File != "" {
			line += " (" + filepath.Base(frame.File) + ":" + strconv.Itoa(frame.Line) + ")"
		}
		line, cut := shorten(line, limit)
		cost := len(line)
		if b.Len() > 0 {
			cost++
		}
		if cut || b.Len()+cost > limit {
			if b.Len() == 0 {
				return line, true
			}
			return b.String(), true
		}
		if b.Len() > 0 {
			b.WriteByte('\n')
		}
		b.WriteString(line)
	}
	return b.String(), n == len(pcs)
}

func encode(v any) (*bytes.Buffer, error) {
	var buf bytes.Buffer
	encoder := json.NewEncoder(&buf)
	encoder.SetEscapeHTML(false)
	return &buf, encoder.Encode(v)
}

// fit encodes the record with its degradation flags. Over the record limit it
// drops the outermost stack frame first, then the largest caller attribute
// (ties: key name descending), counting each, until the line fits.
func (h *Handler) fit(attrs map[string]any, removable []string, state fieldState) (*bytes.Buffer, error) {
	for {
		if state.truncated {
			attrs[truncatedField] = true
		}
		if state.dropped > 0 {
			attrs[droppedField] = min(state.dropped, h.maxDrops)
		}
		buf, err := encode(attrs)
		if err != nil || buf.Len()-1 <= h.recordLimit {
			return buf, err
		}
		if stack, ok := attrs[stacktraceField].(string); ok {
			if i := strings.LastIndexByte(stack, '\n'); i >= 0 {
				attrs[stacktraceField] = stack[:i]
			} else {
				delete(attrs, stacktraceField)
			}
			state.truncated = true
			continue
		}
		largest, largestSize := "", -1
		for _, k := range removable {
			v, ok := attrs[k]
			if !ok {
				continue
			}
			field, err := encode(map[string]any{k: v})
			if err != nil {
				return nil, err
			}
			if size := field.Len(); size > largestSize || size == largestSize && k > largest {
				largest, largestSize = k, size
			}
		}
		if largestSize < 0 {
			return buf, nil // Still too large: the caller drops it as Invalid.
		}
		delete(attrs, largest)
		state.dropped++
	}
}

func (h *Handler) WithAttrs(attrs []slog.Attr) slog.Handler {
	clone := *h
	clone.attrs = make(map[string]any, len(h.attrs))
	for k, v := range h.attrs {
		clone.attrs[k] = v
	}
	var own fieldState
	for _, attr := range attrs {
		clone.add(clone.attrs, &own, clone.group, attr, 0)
	}
	clone.state.merge(own)
	return &clone
}

// WithGroup never disables the logger: under an invalid group name every
// attribute is removed and counted on each record.
func (h *Handler) WithGroup(name string) slog.Handler {
	if name == "" {
		return h
	}
	clone := *h
	if !fieldName.MatchString(name) || len(clone.group)+len(name) > 128 {
		clone.badGroup = true
	} else {
		clone.group += name + "."
	}
	return &clone
}

// Stats returns concurrent-safe counters. Samples can advance during the snapshot.
func (h *Handler) Stats() Stats {
	c := &h.sink.counters
	return Stats{c.written.Load(), c.invalid.Load(), c.busy.Load(), c.ioErrors.Load(), c.closed.Load(), int(h.sink.pending.Load())}
}

// Close is CloseWithin(CloseTimeout).
func (h *Handler) Close() { h.CloseWithin(CloseTimeout) }

// CloseWithin stops accepting lines on this handler and its clones (later calls
// count Closed), writes the queued lines until timeout (it blocks up to timeout), and stops the writer
// goroutine. It reports true when nothing queued was lost. Past the deadline the
// undelivered lines stay in Stats.Pending; a Write that is blocked inside the
// caller's writer cannot be interrupted and may still finish later. Calling it
// again is harmless. It never closes the caller-owned writer.
func (h *Handler) CloseWithin(timeout time.Duration) bool {
	s := h.sink
	s.once.Do(func() {
		s.mu.Lock()
		s.closed.Store(true)
		if s.started.Load() {
			close(s.queue)
		} else {
			close(s.exited) // no writer was ever started
		}
		s.mu.Unlock()
	})
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	select {
	case <-s.exited:
	case <-timer.C:
		s.stopOnce.Do(func() { close(s.stop) })
	}
	return s.pending.Load() == 0
}

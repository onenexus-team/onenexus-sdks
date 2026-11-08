package observability

import (
	"bytes"
	"context"
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
	// AllowedFields names bounded scalar extensions, including dotted group paths.
	AllowedFields []string
	MinLevel      slog.Level
	// MaxWait bounds waiting behind another write (default 100ms, maximum 1s).
	// It cannot interrupt the caller-owned writer once Write has started.
	MaxWait time.Duration
}

type Stats struct {
	Written, Invalid, Busy, IOErrors, Closed uint64
	Pending                                  int
}
type counters struct{ written, invalid, busy, ioErrors, closed atomic.Uint64 }
type sink struct {
	gate     chan struct{}
	slots    chan struct{}
	done     chan struct{}
	once     sync.Once
	writer   io.Writer
	closed   atomic.Bool
	broken   bool
	counters counters
}

// Handler is an opt-in slog handler. Clones share one writer fence and counters.
// The writer must return promptly (normally process stdout). No retry loop or
// background goroutine is started. Up to 128 calls may be active/waiting; excess
// calls or elapsed MaxWait are counted drops.
type Handler struct {
	config                    Config
	allowed                   map[string]bool
	reserved                  map[string]bool
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
	errorTypeField  = "error.type"
	stacktraceField = "exception.stacktrace"
	truncatedField  = "logging.truncated"
	droppedField    = "logging.dropped_field_count"
	truncationMark  = "\u2026"
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
	if writer == nil || len(config.AllowedFields) > 32 || config.MaxWait < 0 || config.MaxWait > time.Second {
		return nil, errors.New("invalid_log_config")
	}
	if config.MaxWait == 0 {
		config.MaxWait = 100 * time.Millisecond
	}
	b, err := Load()
	if err != nil {
		return nil, err
	}
	h := &Handler{config: config, allowed: make(map[string]bool), reserved: make(map[string]bool), sink: &sink{writer: writer, gate: make(chan struct{}, 1), slots: make(chan struct{}, 128), done: make(chan struct{})}, attrs: make(map[string]any), messageLimit: b.MaxMessageBytes, recordLimit: b.MaxRecordBytes, fieldLimit: b.MaxFieldBytes, stackLimit: b.MaxStacktraceBytes, errorTypeLimit: b.MaxErrorTypeChars, maxDrops: b.MaxDroppedFieldCount}
	h.config.AllowedFields = nil
	for _, field := range b.CommonFields {
		h.reserved[field] = true
	}
	for _, field := range config.AllowedFields {
		if !fieldName.MatchString(field) || h.reserved[field] || h.allowed[field] {
			return nil, errors.New("invalid_allowed_fields")
		}
		h.allowed[field] = true
	}
	data, _ := json.Marshal(map[string]any{"timestamp": 0, "level": "INFO", "message": "Startup validation", "service": config.Service, "region": config.Region, "environment": config.Environment})
	for _, field := range requestFieldNames {
		h.allowed[field] = true
	}
	if !utf8.ValidString(config.Service+config.Region+config.Environment) || len(ValidateJSON(data, "common")) > 0 {
		return nil, errors.New("invalid_log_config")
	}
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
// Operators should export Stats through their metrics.
func (h *Handler) Handle(ctx context.Context, record slog.Record) error {
	s := h.sink
	if s.closed.Load() {
		s.counters.closed.Add(1)
		return nil
	}
	if !utf8.ValidString(record.Message) {
		s.counters.invalid.Add(1)
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
		s.counters.invalid.Add(1)
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
		s.counters.invalid.Add(1)
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
	buf, err := h.fit(attrs, removable, state)
	if err != nil || buf.Len()-1 > h.recordLimit || len(ValidateJSON(buf.Bytes(), profile)) > 0 {
		s.counters.invalid.Add(1)
		return errInvalid
	}
	// Bound waiting callers and their wait time. One line owns the writer at a time.
	select {
	case s.slots <- struct{}{}:
	default:
		s.counters.busy.Add(1)
		return nil
	}
	defer func() { <-s.slots }()
	select {
	case s.gate <- struct{}{}:
	default:
		timer := time.NewTimer(h.config.MaxWait)
		defer timer.Stop()
		select {
		case s.gate <- struct{}{}:
		case <-s.done:
			s.counters.closed.Add(1)
			return nil
		case <-timer.C:
			s.counters.busy.Add(1)
			return nil
		}
	}
	defer func() { <-s.gate }()
	if s.closed.Load() {
		s.counters.closed.Add(1)
		return nil
	}
	if s.broken {
		s.counters.ioErrors.Add(1)
		return errIO
	}
	n, err := s.writer.Write(buf.Bytes())
	if err != nil || n != buf.Len() {
		s.counters.ioErrors.Add(1)
		// A partial JSON line makes subsequent appends unsafe. A new handler/writer
		// is required; do not repeatedly append malformed lines or retry secrets.
		if n != 0 {
			s.broken = true
		}
		return errIO
	}
	s.counters.written.Add(1)
	return nil
}

// add copies one attribute. A value that cannot be emitted is removed and
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
	key := prefix + attr.Key
	if attr.Value.Kind() == slog.KindGroup {
		if attr.Key != "" {
			prefix = key + "."
		}
		for _, a := range attr.Value.Group() {
			h.add(dst, state, prefix, a, depth+1)
		}
		return
	}
	if _, ok := dst[key]; ok || len(dst) >= 34 || (!h.allowed[key] && key != "event" && key != "outcome") {
		state.dropped++
		return
	}
	if (key == errorTypeField || key == stacktraceField) && attr.Value.Kind() != slog.KindString {
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
	return Stats{c.written.Load(), c.invalid.Load(), c.busy.Load(), c.ioErrors.Load(), c.closed.Load(), len(h.sink.slots)}
}

// Close stops accepting new writes, including on clones. An already-entered Write
// may finish after Close returns; caller owns any writer flush/shutdown deadline.
func (h *Handler) Close() { h.sink.once.Do(func() { h.sink.closed.Store(true); close(h.sink.done) }) }

package observability

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"math"
	"regexp"
	"sync"
	"sync/atomic"
	"time"
	"unicode/utf8"

	logcontract "github.com/onenexus-team/onenexus-sdks/contracts/log-correlation"
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
	invalid                   bool
	messageLimit, recordLimit int
}

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
	b, err := logcontract.Load()
	if err != nil {
		return nil, err
	}
	h := &Handler{config: config, allowed: make(map[string]bool), reserved: make(map[string]bool), sink: &sink{writer: writer, gate: make(chan struct{}, 1), slots: make(chan struct{}, 128), done: make(chan struct{})}, attrs: make(map[string]any), messageLimit: b.MaxMessageBytes, recordLimit: b.MaxRecordBytes}
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
	if !utf8.ValidString(config.Service+config.Region+config.Environment) || len(logcontract.ValidateJSON(data, "common")) > 0 {
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

// Handle drops bad records and returns only stable errors; it never echoes values.
// slog ignores handler errors. Operators should export Stats through their metrics.
func (h *Handler) Handle(ctx context.Context, record slog.Record) error {
	s := h.sink
	if s.closed.Load() {
		s.counters.closed.Add(1)
		return nil
	}
	if h.invalid || len(record.Message) > h.messageLimit || !utf8.ValidString(record.Message) {
		s.counters.invalid.Add(1)
		return errInvalid
	}
	attrs := make(map[string]any, len(h.attrs)+min(record.NumAttrs(), 34))
	for k, v := range h.attrs {
		attrs[k] = v
	}
	valid := true
	record.Attrs(func(a slog.Attr) bool { valid = h.add(attrs, h.group, a, 0); return valid })
	_, hasEvent := attrs["event"]
	_, hasOutcome := attrs["outcome"]
	if !valid || hasEvent != hasOutcome {
		s.counters.invalid.Add(1)
		return errInvalid
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
	attrs["message"] = record.Message
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
	var buf bytes.Buffer
	encoder := json.NewEncoder(&buf)
	encoder.SetEscapeHTML(false)
	if encoder.Encode(attrs) != nil || buf.Len()-1 > h.recordLimit || len(logcontract.ValidateJSON(buf.Bytes(), profile)) > 0 {
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

func (h *Handler) add(dst map[string]any, prefix string, attr slog.Attr, depth int) bool {
	if depth > 8 {
		return false
	}
	if attr.Equal(slog.Attr{}) {
		return true
	}
	if len(attr.Key) > 128 || !utf8.ValidString(attr.Key) {
		return false
	}
	key := prefix + attr.Key
	if attr.Value.Kind() == slog.KindGroup {
		if attr.Key != "" {
			prefix = key + "."
		}
		for _, a := range attr.Value.Group() {
			if !h.add(dst, prefix, a, depth+1) {
				return false
			}
		}
		return true
	}
	if _, ok := dst[key]; ok {
		return false
	}
	if len(dst) >= 34 || (!h.allowed[key] && key != "event" && key != "outcome") {
		return false
	}
	var value any
	switch attr.Value.Kind() {
	case slog.KindString:
		value = attr.Value.String()
		if len(value.(string)) > h.messageLimit || !utf8.ValidString(value.(string)) {
			return false
		}
	case slog.KindBool:
		value = attr.Value.Bool()
	case slog.KindInt64:
		value = attr.Value.Int64()
	case slog.KindUint64:
		value = attr.Value.Uint64()
	case slog.KindFloat64:
		value = attr.Value.Float64()
		if math.IsNaN(value.(float64)) || math.IsInf(value.(float64), 0) {
			return false
		}
	case slog.KindAny:
		if attr.Value.Any() != nil {
			return false
		}
	default:
		return false // Never call user LogValuer, Stringer or JSON methods.
	}
	dst[key] = value
	return true
}

func (h *Handler) WithAttrs(attrs []slog.Attr) slog.Handler {
	clone := *h
	clone.attrs = make(map[string]any, len(h.attrs))
	for k, v := range h.attrs {
		clone.attrs[k] = v
	}
	for _, attr := range attrs {
		if !clone.add(clone.attrs, clone.group, attr, 0) {
			clone.invalid = true
		}
	}
	return &clone
}

func (h *Handler) WithGroup(name string) slog.Handler {
	if name == "" {
		return h
	}
	clone := *h
	if !fieldName.MatchString(name) || len(clone.group)+len(name) > 128 {
		clone.invalid = true
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

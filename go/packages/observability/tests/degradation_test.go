package observability_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"regexp"
	"runtime/debug"
	"strings"
	"testing"

	obs "github.com/onenexus-team/onenexus-sdks/go/packages/observability"
)

// keptRow asserts that exactly one valid line was written and decodes it.
func keptRow(t *testing.T, line []byte, profile string) map[string]any {
	t.Helper()
	if bytes.Count(line, []byte{'\n'}) != 1 {
		t.Fatal("expected one line", string(line))
	}
	if got := obs.ValidateJSON(bytes.TrimSpace(line), profile); len(got) != 0 {
		t.Fatal(got)
	}
	var row map[string]any
	if err := json.Unmarshal(line, &row); err != nil {
		t.Fatal(err)
	}
	return row
}

func flagCount(row map[string]any) float64 {
	count, _ := row["logging.dropped_field_count"].(float64)
	return count
}

// expand turns {"repeat": s, "count": n} into the repeated string, recursively in maps.
func expand(v any) any {
	switch value := v.(type) {
	case map[string]any:
		if repeat, ok := value["repeat"].(string); ok {
			return strings.Repeat(repeat, int(value["count"].(float64)))
		}
		result := make(map[string]any, len(value))
		for k, item := range value {
			result[k] = expand(item)
		}
		return result
	default:
		return v
	}
}

// nestedLog logs from inside nested calls so the call-site stack has known frames.
func nestedLog(ctx context.Context, logger *slog.Logger, level slog.Level, message string, depth int, err error, attrs []slog.Attr) {
	if depth > 0 {
		nestedLog(ctx, logger, level, message, depth-1, err, attrs)
		return
	}
	logger.LogAttrs(ctx, level, message, append(attrs, slog.Any("err", err))...)
}

func TestSharedDegradationScenarios(t *testing.T) {
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
			ID, Level string
			Message   any
			Fields    map[string]any
			Error     *struct {
				Message     string
				NestedCalls int `json:"nested_calls"`
			}
			Expect map[string]any
		} `json:"degradation_cases"`
		Allowed   []string          `json:"degradation_allowed_fields"`
		ErrorType map[string]string `json:"degradation_error_type"`
	}
	if err = json.Unmarshal(data, &suite); err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) == 0 || suite.ErrorType["go"] == "" {
		t.Fatal("no shared degradation scenarios")
	}
	levels := map[string]slog.Level{"DEBUG": slog.LevelDebug, "INFO": slog.LevelInfo, "WARN": slog.LevelWarn, "ERROR": slog.LevelError}
	for _, c := range suite.Cases {
		t.Run(c.ID, func(t *testing.T) {
			var output bytes.Buffer
			h, err := obs.NewHandler(obs.Config{Service: "shared-test", Environment: "development", Region: "region-1", AllowedFields: suite.Allowed}, &output)
			if err != nil {
				t.Fatal(err)
			}
			defer h.Close()
			logger := slog.New(h)
			message := expand(c.Message).(string)
			var attrs []slog.Attr
			for k, v := range expand(c.Fields).(map[string]any) {
				attrs = append(attrs, slog.Any(k, v))
			}
			ctx := context.Background()
			level, ok := levels[c.Level]
			if !ok {
				t.Fatal("unknown level", c.Level)
			}
			if c.Error != nil {
				nestedLog(ctx, logger, level, message, c.Error.NestedCalls, errors.New(c.Error.Message), attrs)
			} else {
				logger.LogAttrs(ctx, level, message, attrs...)
			}
			if s := h.Stats(); s.Invalid != 0 || s.Written != 1 {
				t.Fatal("record dropped", s)
			}
			row := keptRow(t, output.Bytes(), "common")
			line := bytes.TrimSuffix(output.Bytes(), []byte{'\n'})
			expect := c.Expect
			if want, got := expect["truncated"], row["logging.truncated"]; want != got {
				t.Fatalf("truncated: %v want %v", got, want)
			}
			if want, got := expect["dropped_field_count"], row["logging.dropped_field_count"]; want != got {
				t.Fatalf("dropped_field_count: %v want %v", got, want)
			}
			got := row["message"].(string)
			if want, ok := expect["message"]; ok {
				if got != expand(want) {
					t.Fatal("message changed", got)
				}
			} else if len(got) > int(expect["message_max_bytes"].(float64)) || !strings.HasPrefix(got, expect["message_prefix"].(string)) || !strings.HasSuffix(got, expect["message_suffix"].(string)) {
				t.Fatal("message not shortened", len(got))
			}
			if fields, ok := expect["fields"]; ok {
				for k, want := range expand(fields).(map[string]any) {
					if row[k] != want {
						t.Fatalf("%s: %v want %v", k, row[k], want)
					}
				}
			}
			if absent, ok := expect["absent"].([]any); ok {
				for _, k := range absent {
					if _, ok := row[k.(string)]; ok {
						t.Fatal("unexpected", k)
					}
				}
			}
			if bounds, ok := expect["field_bounds"].(map[string]any); ok {
				for k, b := range bounds {
					bound := b.(map[string]any)
					value, _ := row[k].(string)
					if len(value) > int(bound["max_bytes"].(float64)) || !strings.HasPrefix(value, bound["prefix"].(string)) || !strings.HasSuffix(value, bound["suffix"].(string)) {
						t.Fatal("field not bounded", k, len(value))
					}
				}
			}
			if limit, ok := expect["record_max_bytes"].(float64); ok && len(line) > int(limit) {
				t.Fatal("record too large", len(line))
			}
			if expect["error_type"] == true {
				if row["error.type"] != suite.ErrorType["go"] {
					t.Fatal("error.type", row["error.type"])
				}
				stack, _ := row["exception.stacktrace"].(string)
				if stack == "" || len(stack) > int(expect["stacktrace_max_bytes"].(float64)) {
					t.Fatal("stacktrace bound", len(stack))
				}
				pattern := regexp.MustCompile(expect["stacktrace_line_pattern"].(string))
				frames := strings.Split(stack, "\n")
				for _, frame := range frames {
					if !pattern.MatchString(frame) {
						t.Fatal("frame format", frame)
					}
				}
				if !strings.HasPrefix(frames[0], "at ") || !strings.Contains(frames[0], "_test.nestedLog (degradation_test.go:") {
					t.Fatal("innermost frame", frames[0])
				}
				for _, marker := range expect["stacktrace_excludes"].([]any) {
					if bytes.Contains(line, []byte(marker.(string))) {
						t.Fatal("error text emitted")
					}
				}
			}
		})
	}
}

func degradationHandler(t *testing.T, allowed ...string) (*obs.Handler, *bytes.Buffer) {
	t.Helper()
	var output bytes.Buffer
	cfg := config()
	cfg.AllowedFields = append(cfg.AllowedFields, allowed...)
	h, err := obs.NewHandler(cfg, &output)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(h.Close)
	return h, &output
}

func TestBadWithAttrsKeepLogger(t *testing.T) {
	h, output := degradationHandler(t)
	logger := slog.New(h)
	withErr := logger.With("err", errors.New("private-sentinel"))
	withBad := logger.With("bad", struct{ Secret string }{"private-sentinel"})
	for range 2 {
		output.Reset()
		withErr.Info("Still logging")
		row := keptRow(t, output.Bytes(), "common")
		if row["error.type"] != "*errors.errorString" || row["exception.stacktrace"] == nil || flagCount(row) != 0 {
			t.Fatal("error attr", output.String())
		}
		output.Reset()
		withBad.Info("Still logging")
		row = keptRow(t, output.Bytes(), "common")
		if flagCount(row) != 1 || row["bad"] != nil || row["error.type"] != nil {
			t.Fatal("bad attr", output.String())
		}
		if strings.Contains(output.String(), "sentinel") {
			t.Fatal("value leaked")
		}
	}
	if s := h.Stats(); s.Written != 4 || s.Invalid != 0 {
		t.Fatal(s)
	}
}

func TestStructAttrKeepsRecord(t *testing.T) {
	h, output := degradationHandler(t)
	slog.New(h).Error("Worker stopped", "stack", struct{ Frames []string }{[]string{"a", "b"}}, "attempt", 2)
	row := keptRow(t, output.Bytes(), "common")
	if flagCount(row) != 1 || row["stack"] != nil || row["attempt"] != float64(2) || row["exception.stacktrace"] != nil {
		t.Fatal(output.String())
	}
}

func panicker() {
	panic(errors.New("private-sentinel"))
}

func recovered(logger *slog.Logger) {
	defer func() {
		if r := recover(); r != nil {
			err, _ := r.(error)
			logger.Error("Recovered panic", "err", err, "stack", debug.Stack())
		}
	}()
	panicker()
}

func TestRecoveredPanicStackIncludesPanickingFrame(t *testing.T) {
	h, output := degradationHandler(t)
	recovered(slog.New(h))
	row := keptRow(t, output.Bytes(), "common")
	stack, _ := row["exception.stacktrace"].(string)
	if !strings.Contains(stack, "_test.panicker (degradation_test.go:") || !strings.Contains(stack, "_test.recovered (degradation_test.go:") {
		t.Fatal("panicking frame missing", stack)
	}
	if strings.Contains(stack, "log/slog.") || strings.Contains(stack, "packages/observability.") {
		t.Fatal("logger frames emitted", stack)
	}
	if row["error.type"] != "*errors.errorString" || flagCount(row) != 1 || strings.Contains(output.String(), "sentinel") {
		t.Fatal(output.String())
	}
}

func TestDuplicateAndExcessAttrsCounted(t *testing.T) {
	h, output := degradationHandler(t)
	logger := slog.New(h)
	logger.With("attempt", 1).Info("Duplicate", "attempt", 2)
	if row := keptRow(t, output.Bytes(), "common"); row["attempt"] != float64(1) || flagCount(row) != 1 {
		t.Fatal(output.String())
	}
	allowed := make([]string, 32)
	args := make([]any, 0, 70)
	for i := range allowed {
		allowed[i] = fmt.Sprintf("f%02d", i)
		args = append(args, allowed[i], i)
	}
	var wide bytes.Buffer
	cfg := config()
	cfg.AllowedFields = allowed
	many, err := obs.NewHandler(cfg, &wide)
	if err != nil {
		t.Fatal(err)
	}
	defer many.Close()
	args = append(args, "http.route", "/x", "http.request.method", "GET", "duration_ms", 1.5)
	slog.New(many).Info("Many", args...)
	row := keptRow(t, wide.Bytes(), "common")
	if flagCount(row) != 1 || row["duration_ms"] != nil || row["f31"] != float64(31) {
		t.Fatal("34-attribute cap", wide.String())
	}
	output.Reset()
	bad := make([]any, 0, 140)
	for i := range 70 {
		bad = append(bad, fmt.Sprintf("unknown%d", i), i)
	}
	logger.Info("Saturated", bad...)
	if row := keptRow(t, output.Bytes(), "common"); flagCount(row) != 64 {
		t.Fatal("count not saturated", output.String())
	}
	// Removed With() attributes accumulate across clones; the count still saturates.
	derived := logger
	for i := range 70 {
		derived = derived.With(fmt.Sprintf("unknown%d", i), i)
	}
	for range 2 {
		output.Reset()
		derived.Info("Saturated clone")
		if row := keptRow(t, output.Bytes(), "common"); flagCount(row) != 64 {
			t.Fatal("clone count not saturated", output.String())
		}
	}
	if h.Stats().Invalid != 0 {
		t.Fatal("saturated count dropped a record", h.Stats())
	}
}

type wrapped[T any] struct{ value T }

func (wrapped[T]) Error() string { return "private-sentinel" }

func TestErrorTypeFields(t *testing.T) {
	h, output := degradationHandler(t, "error.type")
	logger := slog.New(h)
	logger.Error("Caller type", "error.type", "billing.Declined", "err", errors.New("private-sentinel"))
	row := keptRow(t, output.Bytes(), "common")
	if row["error.type"] != "billing.Declined" || row["exception.stacktrace"] == nil {
		t.Fatal("caller error.type must win", output.String())
	}
	// A caller value that breaks its field rule is removed so the SDK value applies.
	for _, bad := range []any{"Not Found", "", strings.Repeat("x", 129), 7} {
		output.Reset()
		logger.Error("Invalid caller type", "error.type", bad, "err", errors.New("private-sentinel"))
		row = keptRow(t, output.Bytes(), "common")
		if row["error.type"] != "*errors.errorString" || flagCount(row) != 1 {
			t.Fatal("invalid caller error.type", output.String())
		}
	}
	if s := h.Stats(); s.Invalid != 0 {
		t.Fatal("invalid caller field dropped the record", s)
	}
	output.Reset()
	logger.Error("Spaced type", "err", wrapped[struct{ A int }]{})
	row = keptRow(t, output.Bytes(), "common")
	if row["error.type"] != "observability_test.wrapped[struct{Aint}]" || strings.Contains(output.String(), "sentinel") {
		t.Fatal("error.type sanitization", output.String())
	}
}

func TestOversizeRecordShortensStackFirst(t *testing.T) {
	var output bytes.Buffer
	h, err := obs.NewHandler(obs.Config{Service: "go-service", Environment: "development", Region: "ric1", AllowedFields: []string{"exception.stacktrace", "a", "b"}}, &output)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	stack := strings.TrimSuffix(strings.Repeat("at app.work (work.go:10)\n", 80), "\n")
	slog.New(h).Error(strings.Repeat("m", 1000), "exception.stacktrace", stack, "a", strings.Repeat("a", 1000), "b", strings.Repeat("b", 1000))
	row := keptRow(t, output.Bytes(), "common")
	kept, _ := row["exception.stacktrace"].(string)
	if output.Len()-1 > 4096 || row["logging.truncated"] != true || flagCount(row) != 0 || row["a"] == nil || row["b"] == nil || kept == "" || !strings.HasPrefix(stack, kept+"\n") {
		t.Fatal("stack not shortened by whole frames", output.Len())
	}
}

type secondError struct{}

func (secondError) Error() string { return "private-sentinel" }

func TestFirstErrorInOneCallNamesTheType(t *testing.T) {
	h, output := degradationHandler(t)
	slog.New(h).Error("Two errors", "first", errors.New("private-sentinel"), "second", secondError{})
	row := keptRow(t, output.Bytes(), "common")
	if row["error.type"] != "*errors.errorString" || strings.Contains(output.String(), "private-sentinel") {
		t.Fatal(output.String())
	}
}

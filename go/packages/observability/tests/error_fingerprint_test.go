package observability_test

// Error fingerprint (tests/logging/scenarios.json error_fingerprint, design review F1).

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"testing"

	obs "github.com/onenexus-team/onenexus-sdks/go/packages/observability"
)

type fingerprintSpec struct {
	Field string `json:"field"`
	Cases []struct {
		ID          string  `json:"id"`
		ErrorType   string  `json:"error_type"`
		Stacktrace  *string `json:"stacktrace"`
		Fingerprint string  `json:"fingerprint"`
	} `json:"cases"`
}

func loadFingerprint(t *testing.T) fingerprintSpec {
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
		Spec fingerprintSpec `json:"error_fingerprint"`
	}
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	return doc.Spec
}

// fingerprintConfig is the shared degradation allowlist: a caller may supply the stack.
func fingerprintConfig() obs.Config {
	c := config()
	c.Service = "go-fingerprint"
	c.AllowedFields = []string{"example.note", "exception.stacktrace"}
	return c
}

func fingerprintRows(t *testing.T, log func(*slog.Logger)) []map[string]any {
	t.Helper()
	h, out := newSyncHandler(t, fingerprintConfig())
	log(slog.New(h))
	h.Close()
	if s := h.Stats(); s.Invalid != 0 {
		t.Fatal("invalid", s)
	}
	var rows []map[string]any
	for _, line := range bytes.Split(bytes.TrimSuffix(out.Bytes(), []byte{'\n'}), []byte{'\n'}) {
		var row map[string]any
		if err := json.Unmarshal(line, &row); err != nil {
			t.Fatal(err)
		}
		rows = append(rows, row)
	}
	return rows
}

func stackOf(row map[string]any) string {
	stack, _ := row["exception.stacktrace"].(string)
	return stack
}

// type_only, frames, line_numbers_ignored, frame_without_file,
// type_changes_fingerprint, multibyte
func TestErrorFingerprintVectors(t *testing.T) {
	for _, c := range loadFingerprint(t).Cases {
		stack := ""
		if c.Stacktrace != nil {
			stack = *c.Stacktrace
		}
		if got := obs.ErrorFingerprint(c.ErrorType, stack); got != c.Fingerprint {
			t.Error(c.ID, got, c.Fingerprint)
		}
	}
}

// logged_error_has_fingerprint
func TestErrorFingerprintLoggedErrorHasFingerprint(t *testing.T) {
	field := loadFingerprint(t).Field
	rows := fingerprintRows(t, func(l *slog.Logger) { l.Error("Job failed", "err", errors.New("private-sentinel")) })
	row := rows[0]
	if row[field] != obs.ErrorFingerprint(row["error.type"].(string), stackOf(row)) {
		t.Fatal(row)
	}
	if strings.Contains(fmt.Sprint(row), "private-sentinel") {
		t.Fatal("message leaked")
	}
}

// same_error_same_fingerprint
func TestErrorFingerprintSameErrorSameFingerprint(t *testing.T) {
	field := loadFingerprint(t).Field
	rows := fingerprintRows(t, func(l *slog.Logger) {
		for range 2 {
			l.Error("Job failed", "err", errors.New("private-sentinel"))
		}
	})
	if len(rows) != 2 || rows[0][field] != rows[1][field] || rows[0][field] == nil {
		t.Fatal(rows)
	}
}

// stable_when_fitted
func TestErrorFingerprintStableWhenFitted(t *testing.T) {
	field := loadFingerprint(t).Field
	frames := make([]string, 55)
	for i := range frames {
		frames[i] = fmt.Sprintf("at function_%d (deep_module.py:%d)", i, i)
	}
	stack := strings.Join(frames, "\n")
	if len(stack) >= 2048 {
		t.Fatal("the stack must be whole: only fitting may shorten it")
	}
	rows := fingerprintRows(t, func(l *slog.Logger) {
		l.Error(strings.Repeat("x", 1000), "err", errors.New("private-sentinel"),
			"exception.stacktrace", stack, "example.note", strings.Repeat("n", 1000))
	})
	row := rows[0]
	if stackOf(row) == stack || row["logging.truncated"] != true {
		t.Fatal("the record was not fitted", row)
	}
	if row[field] != obs.ErrorFingerprint(row["error.type"].(string), stack) {
		t.Fatal(row[field])
	}
}

// caller_value_removed
func TestErrorFingerprintCallerValueRemoved(t *testing.T) {
	field := loadFingerprint(t).Field
	rows := fingerprintRows(t, func(l *slog.Logger) {
		l.Error("Job failed", "err", errors.New("private-sentinel"), field, "0000000000000000")
	})
	row := rows[0]
	if row[field] == "0000000000000000" || row[field] == nil || row["logging.dropped_field_count"] != float64(1) {
		t.Fatal(row)
	}
}

// no_error_no_fingerprint
func TestErrorFingerprintNoErrorNoFingerprint(t *testing.T) {
	field := loadFingerprint(t).Field
	rows := fingerprintRows(t, func(l *slog.Logger) { l.Info("Job done") })
	if _, ok := rows[0][field]; ok {
		t.Fatal(rows[0])
	}
}

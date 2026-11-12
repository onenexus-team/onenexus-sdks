package observability_test

// One field registry (tests/logging/scenarios.json field_registry, design review E1).

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"reflect"
	"slices"
	"strings"
	"testing"

	obs "github.com/onenexus-team/onenexus-sdks/go/packages/observability"
)

type configCase struct {
	ID          string          `json:"id"`
	Names       json.RawMessage `json:"names"`
	Accepted    bool            `json:"accepted"`
	Reason      string          `json:"reason"`
	Replacement string          `json:"replacement"`
}

type valueCase struct {
	ID      string         `json:"id"`
	Fields  map[string]any `json:"fields"`
	Kept    []string       `json:"kept"`
	Dropped json.Number    `json:"dropped_field_count"`
}

type fieldRegistrySpec struct {
	ConfigError  string       `json:"config_error"`
	ConfigCases  []configCase `json:"config_cases"`
	ValueCases   []valueCase  `json:"value_cases"`
	ValueAllowed []string     `json:"value_allowed_fields"`
}

func loadFieldRegistry(t *testing.T) fieldRegistrySpec {
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
		FieldRegistry fieldRegistrySpec `json:"field_registry"`
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	if err := decoder.Decode(&doc); err != nil {
		t.Fatal(err)
	}
	return doc.FieldRegistry
}

// expandNames follows field_registry.names_expansion.
func expandNames(t *testing.T, raw json.RawMessage) []string {
	t.Helper()
	var names []string
	if json.Unmarshal(raw, &names) == nil {
		return names
	}
	var spec struct {
		Prefix, Repeat string
		Count          int
	}
	if err := json.Unmarshal(raw, &spec); err != nil || spec.Count <= 0 {
		t.Fatal("bad names", string(raw))
	}
	if spec.Repeat != "" {
		return []string{spec.Prefix + strings.Repeat(spec.Repeat, spec.Count)}
	}
	for i := range spec.Count {
		names = append(names, fmt.Sprintf("%s%d", spec.Prefix, i))
	}
	return names
}

// Every shared case is tested by its id: a case added to scenarios.json fails
// here until it has a test.
var configCaseIDs = []string{
	"accepts_service_namespace",
	"accepts_registered_field",
	"accepts_otel_namespace",
	"accepts_registered_in_reserved",
	"accepts_max_custom_fields",
	"rejects_protected",
	"rejects_bad_format",
	"rejects_too_many_segments",
	"rejects_too_long",
	"rejects_banned",
	"rejects_banned_namespaced",
	"rejects_reserved_namespace",
	"rejects_unregistered_flat",
	"rejects_unregistered_namespace",
	"rejects_too_many",
}

var valueCaseIDs = []string{
	"scalar_values_kept",
	"object_value_removed",
	"array_value_removed",
	"registered_type_enforced",
	"registered_type_accepted",
}

func TestEveryFieldRegistryCaseHasATest(t *testing.T) {
	spec := loadFieldRegistry(t)
	var config, value []string
	for _, c := range spec.ConfigCases {
		config = append(config, c.ID)
	}
	for _, c := range spec.ValueCases {
		value = append(value, c.ID)
	}
	if !reflect.DeepEqual(config, configCaseIDs) || !reflect.DeepEqual(value, valueCaseIDs) {
		t.Fatal("field_registry cases changed", config, value)
	}
}

// Config cases: CheckAllowedFields and NewHandler give the same verdict, with
// the stable code, the rule and a banned name's replacement.
func TestFieldRegistryConfigCases(t *testing.T) {
	spec := loadFieldRegistry(t)
	for _, c := range spec.ConfigCases {
		t.Run(c.ID, func(t *testing.T) {
			names := expandNames(t, c.Names)
			err := obs.CheckAllowedFields(names)
			cfg := config()
			cfg.AllowedFields = names
			h, handlerErr := obs.NewHandler(cfg, &syncOutput{})
			if h != nil {
				h.Close()
			}
			if c.Accepted {
				if err != nil || handlerErr != nil {
					t.Fatal("rejected", err, handlerErr)
				}
				return
			}
			var fieldErr *obs.AllowedFieldError
			if !errors.As(err, &fieldErr) || !errors.Is(err, obs.ErrInvalidAllowedFields) {
				t.Fatal("accepted or wrong error", err)
			}
			if string(fieldErr.Rule) != c.Reason || fieldErr.Replacement != c.Replacement {
				t.Fatal("rule", fieldErr.Rule, fieldErr.Replacement)
			}
			if !strings.HasPrefix(err.Error(), spec.ConfigError+": "+c.Reason+": ") {
				t.Fatal("detail", err)
			}
			if handlerErr == nil || handlerErr.Error() != err.Error() {
				t.Fatal("NewHandler", handlerErr)
			}
		})
	}
}

func TestBannedFieldErrorNamesReplacement(t *testing.T) {
	err := obs.CheckAllowedFields([]string{"example.ok", "status_code"})
	if err == nil || err.Error() != "invalid_allowed_fields: banned: status_code -> http.response.status_code" {
		t.Fatal(err)
	}
}

func TestDuplicateAllowedFieldRejected(t *testing.T) {
	var fieldErr *obs.AllowedFieldError
	if err := obs.CheckAllowedFields([]string{"example.x", "example.x"}); !errors.As(err, &fieldErr) || fieldErr.Rule != obs.FieldDuplicate || fieldErr.Field != "example.x" {
		t.Fatal(err)
	}
}

// attr turns a scenarios.json value into the slog value a Go caller would pass.
func attr(t *testing.T, key string, value any) slog.Attr {
	t.Helper()
	switch v := value.(type) {
	case json.Number:
		if i, err := v.Int64(); err == nil {
			return slog.Int64(key, i)
		}
		f, err := v.Float64()
		if err != nil {
			t.Fatal(err)
		}
		return slog.Float64(key, f)
	case nil, string, bool, map[string]any, []any:
		return slog.Any(key, v)
	}
	t.Fatalf("unexpected value %T", value)
	return slog.Attr{}
}

// keptFields returns the allowed fields present in row (a null value counts).
func keptFields(row map[string]any, allowed []string) []string {
	kept := []string{}
	for _, name := range allowed {
		if _, ok := row[name]; ok {
			kept = append(kept, name)
		}
	}
	slices.Sort(kept)
	return kept
}

func valueHandler(t *testing.T, allowed []string) (*slog.Logger, *syncOutput) {
	t.Helper()
	cfg := config()
	cfg.AllowedFields = allowed
	h, output := newSyncHandler(t, cfg)
	t.Cleanup(h.Close)
	return slog.New(h), output
}

func checkValueRow(t *testing.T, line []byte, allowed []string, c valueCase) {
	t.Helper()
	row := keptRow(t, line, "common")
	if got := keptFields(row, allowed); !slices.Equal(got, c.Kept) {
		t.Fatal("kept", got, "want", c.Kept)
	}
	want := 0.0
	if c.Dropped != "" {
		want, _ = c.Dropped.Float64()
	}
	if flagCount(row) != want {
		t.Fatal("dropped_field_count", string(line))
	}
}

// Value cases, on the record and on logger.With; the line is always kept.
func TestFieldRegistryValueCases(t *testing.T) {
	spec := loadFieldRegistry(t)
	for _, c := range spec.ValueCases {
		t.Run(c.ID, func(t *testing.T) {
			logger, output := valueHandler(t, spec.ValueAllowed)
			var attrs []any
			for k, v := range c.Fields {
				attrs = append(attrs, attr(t, k, v))
			}
			logger.Info("Value case", attrs...)
			checkValueRow(t, output.Bytes(), spec.ValueAllowed, c)
			output.Reset()
			logger.With(attrs...).Info("Value case on With")
			checkValueRow(t, output.Bytes(), spec.ValueAllowed, c)
		})
	}
}

// A named slog.Group is an object value: removed and counted once, also on
// logger.With. A group without a key is inlined, as slog defines.
func TestGroupValueIsAnObject(t *testing.T) {
	logger, output := valueHandler(t, []string{"example.a", "example.b", "example.s"})
	group := slog.Group("example", slog.Int("a", 1), slog.Int("b", 2))
	logger.Info("Group", group, slog.String("example.s", "x"))
	row := keptRow(t, output.Bytes(), "common")
	if row["example.a"] != nil || row["example.b"] != nil || row["example.s"] != "x" || flagCount(row) != 1 {
		t.Fatal(output.String())
	}
	output.Reset()
	logger.With(group).Info("Group on With")
	if row = keptRow(t, output.Bytes(), "common"); row["example.a"] != nil || flagCount(row) != 1 {
		t.Fatal(output.String())
	}
	output.Reset()
	logger.Info("Inline", slog.Group("", slog.Int("example.a", 1)))
	if row = keptRow(t, output.Bytes(), "common"); row["example.a"] != float64(1) || flagCount(row) != 0 {
		t.Fatal(output.String())
	}
	output.Reset()
	logger.WithGroup("example").Info("WithGroup", slog.Int("a", 1))
	if row = keptRow(t, output.Bytes(), "common"); row["example.a"] != float64(1) || flagCount(row) != 0 {
		t.Fatal(output.String())
	}
}

// Go numbers: a whole float64 is an integer; a registered string takes no number.
func TestRegisteredTypeGoKinds(t *testing.T) {
	logger, output := valueHandler(t, []string{"job.attempt", "duration_ms", "error.type"})
	logger.Info("Kinds", slog.Float64("job.attempt", 3), slog.Uint64("duration_ms", 5), slog.Int("error.type", 7))
	row := keptRow(t, output.Bytes(), "common")
	if row["job.attempt"] != float64(3) || row["duration_ms"] != float64(5) || row["error.type"] != nil || flagCount(row) != 1 {
		t.Fatal(output.String())
	}
}

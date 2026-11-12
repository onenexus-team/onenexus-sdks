package observability

import (
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"regexp"
	"strings"
	"unicode/utf8"
)

// ErrInvalidAllowedFields is the stable configuration error code for
// Config.AllowedFields. Every *AllowedFieldError wraps it.
var ErrInvalidAllowedFields = errors.New("invalid_allowed_fields")

// FieldRule names the registry rule an allowed field name failed
// (tests/logging/scenarios.json field_registry).
type FieldRule string

const (
	FieldProtected FieldRule = "protected"
	FieldFormat    FieldRule = "format"
	FieldReserved  FieldRule = "reserved"
	FieldNamespace FieldRule = "namespace"
	FieldTooMany   FieldRule = "too_many"
	// FieldDuplicate is Go only: a name listed twice.
	FieldDuplicate FieldRule = "duplicate"
)

// AllowedFieldError is the first allowed field name that breaks the registry.
// Field is that name (for FieldTooMany, the count).
type AllowedFieldError struct {
	Rule  FieldRule
	Field string
}

func (e *AllowedFieldError) Error() string {
	text := ErrInvalidAllowedFields.Error() + ": " + string(e.Rule)
	if e.Field != "" {
		text += ": " + e.Field
	}
	return text
}

func (e *AllowedFieldError) Unwrap() error { return ErrInvalidAllowedFields }

// valueType is a registered field's value type (x-field-registry value_types).
type valueType string

const (
	typeString  valueType = "string"
	typeInteger valueType = "integer"
	typeNumber  valueType = "number"
	typeBoolean valueType = "boolean"
	typeNull    valueType = "null"
)

// fieldRegistry is the schema's x-field-registry (design review E1).
type fieldRegistry struct {
	protected   map[string]bool // x-protected-fields
	namePattern *regexp.Regexp
	maxChars    int
	maxFields   int
	namespaces  map[string]bool
	reserved    map[string]bool
	types       map[string]valueType
}

func loadRegistry(raw json.RawMessage, protected []string) (*fieldRegistry, error) {
	var doc struct {
		Pattern    string            `json:"name_pattern"`
		MaxChars   int               `json:"name_max_chars"`
		MaxFields  int               `json:"max_custom_fields"`
		Namespaces map[string]string `json:"namespaces"`
		Reserved   map[string]string `json:"reserved_namespaces"`
		Fields     map[string]struct {
			Type valueType `json:"type"`
		} `json:"fields"`
	}
	invalid := errors.New("invalid_field_registry")
	if json.Unmarshal(raw, &doc) != nil || doc.MaxChars <= 0 || doc.MaxFields <= 0 || len(doc.Fields) == 0 {
		return nil, invalid
	}
	pattern, err := regexp.Compile(doc.Pattern)
	if err != nil {
		return nil, invalid
	}
	r := &fieldRegistry{namePattern: pattern, maxChars: doc.MaxChars, maxFields: doc.MaxFields,
		protected: make(map[string]bool), namespaces: make(map[string]bool), reserved: make(map[string]bool), types: make(map[string]valueType)}
	for _, name := range protected {
		r.protected[name] = true
	}
	for name := range doc.Namespaces {
		r.namespaces[name] = true
	}
	for name := range doc.Reserved {
		r.reserved[name] = true
	}
	for name, field := range doc.Fields {
		switch field.Type {
		case typeString, typeInteger, typeNumber, typeBoolean, typeNull:
			r.types[name] = field.Type
		default:
			return nil, invalid
		}
	}
	return r, nil
}

// CheckAllowedFields checks custom field names against the bundled field
// registry, in the shared check order. It returns nil or the first failure as an
// *AllowedFieldError (errors.Is(err, ErrInvalidAllowedFields)). NewHandler
// applies it to Config.AllowedFields.
func CheckAllowedFields(names []string) error {
	loadOnce.Do(initialize)
	if loadError != nil {
		return errors.New("invalid_embedded_contract")
	}
	r := registry
	if len(names) > r.maxFields {
		return &AllowedFieldError{Rule: FieldTooMany, Field: fmt.Sprintf("%d names, max %d", len(names), r.maxFields)}
	}
	seen := make(map[string]bool, len(names))
	for _, name := range names {
		if rule := r.check(name); rule != "" {
			return &AllowedFieldError{Rule: rule, Field: name}
		}
		if seen[name] {
			return &AllowedFieldError{Rule: FieldDuplicate, Field: name}
		}
		seen[name] = true
	}
	return nil
}

// check returns the first rule name breaks, or "".
func (r *fieldRegistry) check(name string) FieldRule {
	if r.protected[name] {
		return FieldProtected
	}
	if utf8.RuneCountInString(name) > r.maxChars || !r.namePattern.MatchString(name) {
		return FieldFormat
	}
	if _, ok := r.types[name]; ok {
		return ""
	}
	head, _, dotted := strings.Cut(name, ".")
	if r.reserved[head] {
		return FieldReserved
	}
	if !dotted || !r.namespaces[head] {
		return FieldNamespace
	}
	return ""
}

// accepts reports whether v may be the value of field key: a registered field
// must match its type; null is always allowed.
func (r *fieldRegistry) accepts(key string, v slog.Value) bool {
	t, ok := r.types[key]
	if !ok || v.Kind() == slog.KindAny && v.Any() == nil {
		return true
	}
	switch t {
	case typeString:
		return v.Kind() == slog.KindString
	case typeBoolean:
		return v.Kind() == slog.KindBool
	case typeNumber:
		return v.Kind() == slog.KindInt64 || v.Kind() == slog.KindUint64 || v.Kind() == slog.KindFloat64
	case typeInteger:
		return v.Kind() == slog.KindInt64 || v.Kind() == slog.KindUint64 || v.Kind() == slog.KindFloat64 && v.Float64() == math.Trunc(v.Float64())
	default: // typeNull
		return false
	}
}

// Package logcontract validates records against the canonical, embedded contract.
// Schema and test vectors are embedded from their original files, never copied.
package logcontract

import (
	"bytes"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"sort"
	"strings"
	"sync"
	"unicode/utf8"

	"github.com/santhosh-tekuri/jsonschema/v6"
	"github.com/santhosh-tekuri/jsonschema/v6/kind"
)

//go:embed manifest.json schema.json vectors.json
var source embed.FS

type Identity struct {
	Version string `json:"version"`
	Digest  string `json:"sha256"`
}

// Bundle contains independent copies. Mutating it cannot alter validation.
type Bundle struct {
	Identity
	Schema          json.RawMessage
	Vectors         json.RawMessage
	CommonFields    []string
	MaxMessageBytes int
	MaxRecordBytes  int
}

var loadOnce sync.Once
var bundle Bundle
var validators map[string]*jsonschema.Schema
var loadError error

type noNetwork struct{}

func (noNetwork) Load(string) (any, error) { return nil, errors.New("external_schema_forbidden") }

func initialize() {
	manifest, _ := source.ReadFile("manifest.json")
	var m struct {
		Identity
		Files []struct{ Path, SHA256 string }
	}
	if err := json.Unmarshal(manifest, &m); err != nil {
		loadError = err
		return
	}
	h := sha256.New()
	if len(m.Files) != 2 || m.Files[0].Path != "schema.json" || m.Files[1].Path != "vectors.json" {
		loadError = errors.New("invalid_manifest")
		return
	}
	for _, f := range m.Files {
		data, err := source.ReadFile(f.Path)
		sum := sha256.Sum256(data)
		if err != nil || hex.EncodeToString(sum[:]) != f.SHA256 {
			loadError = errors.New("contract_digest_mismatch")
			return
		}
		h.Write([]byte(f.Path))
		h.Write([]byte{0})
		h.Write(data)
	}
	if hex.EncodeToString(h.Sum(nil)) != m.Digest {
		loadError = errors.New("contract_digest_mismatch")
		return
	}
	schema, _ := source.ReadFile("schema.json")
	vectors, _ := source.ReadFile("vectors.json")
	var details struct {
		Version string                                         `json:"x-contract-version"`
		Defs    map[string]struct{ Properties map[string]any } `json:"$defs"`
		Limits  struct {
			Message int `json:"message_max_utf8_bytes"`
			Record  int `json:"record_max_compact_utf8_bytes"`
		} `json:"x-semantic-checks"`
	}
	var cases struct {
		Version string `json:"contract_version"`
	}
	if json.Unmarshal(schema, &details) != nil || json.Unmarshal(vectors, &cases) != nil || details.Version != m.Version || cases.Version != m.Version || details.Limits.Message <= 0 || details.Limits.Record <= 0 {
		loadError = errors.New("invalid_contract")
		return
	}
	doc, err := jsonschema.UnmarshalJSON(bytes.NewReader(schema))
	if err != nil {
		loadError = err
		return
	}
	c := jsonschema.NewCompiler()
	c.UseLoader(noNetwork{})
	const location = "https://contract.invalid/schema.json"
	if err = c.AddResource(location, doc); err != nil {
		loadError = err
		return
	}
	validators = make(map[string]*jsonschema.Schema)
	for name := range details.Defs {
		v, err := c.Compile(location + "#/$defs/" + name)
		if err != nil {
			loadError = err
			return
		}
		validators[name] = v
	}
	fields := make([]string, 0, len(details.Defs["common"].Properties))
	for name := range details.Defs["common"].Properties {
		fields = append(fields, name)
	}
	sort.Strings(fields)
	bundle = Bundle{Identity: m.Identity, Schema: schema, Vectors: vectors, CommonFields: fields, MaxMessageBytes: details.Limits.Message, MaxRecordBytes: details.Limits.Record}
}

// Load verifies hashes and compiles schemas once, without network access.
func Load() (Bundle, error) {
	loadOnce.Do(initialize)
	if loadError != nil {
		return Bundle{}, errors.New("invalid_embedded_contract")
	}
	b := bundle
	b.Schema = bytes.Clone(b.Schema)
	b.Vectors = bytes.Clone(b.Vectors)
	b.CommonFields = append([]string(nil), b.CommonFields...)
	return b, nil
}

func code(field string) string {
	switch field {
	case "message":
		return "missing_or_invalid_message"
	case "trace_id":
		return "missing_or_invalid_trace_id"
	default:
		return "schema_invalid"
	}
}

// ValidateJSON returns stable, sorted error codes without including input data.
// The caller selects the profile; a producer cannot downgrade its own scenario.
func ValidateJSON(data []byte, profile string) []string {
	loadOnce.Do(initialize)
	if loadError != nil {
		return []string{"invalid_embedded_contract"}
	}
	v, ok := validators[profile]
	if !ok {
		return []string{"unknown_profile"}
	}
	if len(data) > 65536 {
		return []string{"record_too_large"}
	}
	if !utf8.Valid(data) || !validEscapes(data) {
		return []string{"invalid_json_record"}
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	obj, err := decodeUnique(decoder, 0)
	if err != nil {
		return []string{"invalid_json_record"}
	}
	if _, err = decoder.Token(); err != io.EOF {
		return []string{"invalid_json_record"}
	}
	record, ok := obj.(map[string]any)
	if !ok {
		return []string{"schema_invalid"}
	}
	errorsFound := make(map[string]bool)
	if err = v.Validate(record); err != nil {
		var ve *jsonschema.ValidationError
		if !errors.As(err, &ve) {
			return []string{"schema_invalid"}
		}
		var collect func(*jsonschema.ValidationError)
		collect = func(e *jsonschema.ValidationError) {
			if len(e.Causes) > 0 {
				for _, child := range e.Causes {
					collect(child)
				}
				return
			}
			if required, ok := e.ErrorKind.(*kind.Required); ok {
				for _, field := range required.Missing {
					errorsFound[code(field)] = true
				}
			} else if len(e.InstanceLocation) > 0 {
				errorsFound[code(e.InstanceLocation[0])] = true
			} else {
				errorsFound["schema_invalid"] = true
			}
		}
		collect(ve)
	}
	if message, ok := record["message"].(string); ok && (len(message) > bundle.MaxMessageBytes || strings.TrimSpace(message) == "") {
		errorsFound["missing_or_invalid_message"] = true
	}
	encoded, err := compactJSON(record)
	if err != nil {
		errorsFound["invalid_json_record"] = true
	} else if len(encoded) > bundle.MaxRecordBytes {
		errorsFound["record_too_large"] = true
	}
	result := make([]string, 0, len(errorsFound))
	for value := range errorsFound {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func compactJSON(v any) ([]byte, error) {
	var b bytes.Buffer
	e := json.NewEncoder(&b)
	e.SetEscapeHTML(false)
	if err := e.Encode(v); err != nil {
		return nil, err
	}
	// Go escapes these valid Unicode separators even with EscapeHTML disabled.
	// Contract byte limits use their UTF-8 encoding, as Python ensure_ascii=false.
	data := bytes.TrimSuffix(b.Bytes(), []byte{'\n'})
	var normalized bytes.Buffer
	for i := 0; i < len(data); i++ {
		if data[i] == '\\' && i+1 < len(data) {
			if i+5 < len(data) && (string(data[i:i+6]) == `\u2028` || string(data[i:i+6]) == `\u2029`) {
				if data[i+5] == '8' {
					normalized.WriteRune('\u2028')
				} else {
					normalized.WriteRune('\u2029')
				}
				i += 5
				continue
			}
			normalized.WriteByte(data[i])
			i++
		}
		normalized.WriteByte(data[i])
	}
	data = normalized.Bytes()
	return data, nil
}

func decodeUnique(d *json.Decoder, depth int) (any, error) {
	if depth > 32 {
		return nil, errors.New("too_deep")
	}
	t, err := d.Token()
	if err != nil {
		return nil, err
	}
	switch t {
	case json.Delim('{'):
		m := make(map[string]any)
		for d.More() {
			key, e := d.Token()
			if e != nil {
				return nil, e
			}
			k, ok := key.(string)
			if !ok {
				return nil, errors.New("invalid_key")
			}
			if _, exists := m[k]; exists {
				return nil, errors.New("duplicate_key")
			}
			value, e := decodeUnique(d, depth+1)
			if e != nil {
				return nil, e
			}
			m[k] = value
		}
		_, err = d.Token()
		return m, err
	case json.Delim('['):
		a := make([]any, 0)
		for d.More() {
			value, e := decodeUnique(d, depth+1)
			if e != nil {
				return nil, e
			}
			a = append(a, value)
		}
		_, err = d.Token()
		return a, err
	default:
		return t, nil
	}
}

// encoding/json replaces invalid surrogate escapes. Reject before it can coerce.
func validEscapes(data []byte) bool {
	for i := 0; i < len(data); i++ {
		if data[i] != '\\' {
			continue
		}
		i++
		if i >= len(data) {
			return false
		}
		if data[i] != 'u' {
			continue
		}
		if i+4 >= len(data) {
			return false
		}
		var n uint16
		if _, err := fmt.Sscanf(string(data[i+1:i+5]), "%04x", &n); err != nil {
			return false
		}
		i += 4
		if n >= 0xdc00 && n <= 0xdfff {
			return false
		}
		if n >= 0xd800 && n <= 0xdbff {
			if i+6 >= len(data) || data[i+1] != '\\' || data[i+2] != 'u' {
				return false
			}
			var low uint16
			if _, err := fmt.Sscanf(string(data[i+3:i+7]), "%04x", &low); err != nil || low < 0xdc00 || low > 0xdfff {
				return false
			}
			i += 6
		}
	}
	return true
}

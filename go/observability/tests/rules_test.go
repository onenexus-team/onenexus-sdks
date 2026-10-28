package observability_test

import (
	"bytes"
	"reflect"
	"strings"
	"testing"

	obs "github.com/onenexus-team/onenexus-sdks/go/observability"
)

func TestLoadReturnsIndependentData(t *testing.T) {
	a, _ := obs.Load()
	before := bytes.Clone(a.Schema)
	a.Schema[0] = '!'
	a.CommonFields[0] = "changed"
	b, err := obs.Load()
	if err != nil || !bytes.Equal(b.Schema, before) || b.CommonFields[0] == "changed" {
		t.Fatal("mutable validator data")
	}
}

func TestStrictJSONAndProfiles(t *testing.T) {
	for _, input := range []string{`{"message":"a","message":"b"}`, `{"x":{"a":1,"a":2}}`, `{"x":"\ud800"}`, `{"x":"\udc00"}`, `{"x":NaN}`, `{} {}`, string([]byte{0xff}), strings.Repeat("[", 34) + strings.Repeat("]", 34)} {
		if got := obs.ValidateJSON([]byte(input), "common"); !reflect.DeepEqual(got, []string{"invalid_json_record"}) {
			t.Fatalf("unexpected codes %v", got)
		}
	}
	if got := obs.ValidateJSON([]byte(`{}`), "anything"); !reflect.DeepEqual(got, []string{"unknown_profile"}) {
		t.Fatal(got)
	}
	if got := obs.ValidateJSON([]byte(`[]`), "common"); !reflect.DeepEqual(got, []string{"schema_invalid"}) {
		t.Fatal(got)
	}
	base := `{"timestamp":9223372036854775807,"level":"INFO","service":"go","environment":"development","region":"ric1","message":"\ud83d\ude00"}`
	if got := obs.ValidateJSON([]byte(base), "common"); len(got) != 0 {
		t.Fatal(got)
	}
	if got := obs.ValidateJSON([]byte(strings.Replace(base, "9223372036854775807", "9223372036854775808", 1)), "common"); !reflect.DeepEqual(got, []string{"schema_invalid"}) {
		t.Fatal(got)
	}
}

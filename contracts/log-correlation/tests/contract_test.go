package logcontract_test

import (
	"bytes"
	"encoding/json"
	"reflect"
	"strings"
	"testing"

	contract "github.com/onenexus-team/onenexus-sdks/contracts/log-correlation"
)

func TestSharedRecordCases(t *testing.T) {
	b, err := contract.Load()
	if err != nil {
		t.Fatal(err)
	}
	var vectors struct {
		Cases []struct {
			ID, Profile string
			Record      json.RawMessage
			Errors      []string
		} `json:"record_cases"`
	}
	if err = json.Unmarshal(b.Vectors, &vectors); err != nil {
		t.Fatal(err)
	}
	for _, c := range vectors.Cases {
		t.Run(c.ID, func(t *testing.T) {
			if got := contract.ValidateJSON(c.Record, c.Profile); !reflect.DeepEqual(got, c.Errors) {
				t.Fatalf("got %v want %v", got, c.Errors)
			}
		})
	}
}

func TestLoadReturnsIndependentData(t *testing.T) {
	a, _ := contract.Load()
	before := bytes.Clone(a.Schema)
	a.Schema[0] = '!'
	a.Vectors[0] = '!'
	a.CommonFields[0] = "changed"
	b, err := contract.Load()
	if err != nil || !bytes.Equal(b.Schema, before) || b.Vectors[0] == '!' || b.CommonFields[0] == "changed" {
		t.Fatal("mutable validator data")
	}
}

func TestStrictJSONAndProfiles(t *testing.T) {
	for _, input := range []string{`{"message":"a","message":"b"}`, `{"x":{"a":1,"a":2}}`, `{"x":"\ud800"}`, `{"x":"\udc00"}`, `{"x":NaN}`, `{} {}`, string([]byte{0xff}), strings.Repeat("[", 34) + strings.Repeat("]", 34)} {
		if got := contract.ValidateJSON([]byte(input), "common"); !reflect.DeepEqual(got, []string{"invalid_json_record"}) {
			t.Fatalf("unexpected codes %v", got)
		}
	}
	if got := contract.ValidateJSON([]byte(`{}`), "anything"); !reflect.DeepEqual(got, []string{"unknown_profile"}) {
		t.Fatal(got)
	}
	if got := contract.ValidateJSON([]byte(`[]`), "common"); !reflect.DeepEqual(got, []string{"schema_invalid"}) {
		t.Fatal(got)
	}
	base := `{"timestamp":9223372036854775807,"level":"INFO","service":"go","environment":"development","region":"ric1","message":"\ud83d\ude00"}`
	if got := contract.ValidateJSON([]byte(base), "common"); len(got) != 0 {
		t.Fatal(got)
	}
	if got := contract.ValidateJSON([]byte(strings.Replace(base, "9223372036854775807", "9223372036854775808", 1)), "common"); !reflect.DeepEqual(got, []string{"schema_invalid"}) {
		t.Fatal(got)
	}
}

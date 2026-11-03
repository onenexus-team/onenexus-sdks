package observability_test

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"reflect"
	"strings"
	"sync"
	"testing"

	obs "github.com/onenexus-team/onenexus-sdks/go/observability"
)

var requestTenant = strings.Repeat("1", 32)
var requestOwner = "nx1://test/" + requestTenant + "/CAS/global/User/" + strings.Repeat("2", 32)

func TestSharedRequestEmissions(t *testing.T) {
	path := os.Getenv("ONENEXUS_LOGGING_SCENARIOS")
	if path == "" {
		path = "../../../tests/logging/scenarios.json"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var suite struct {
		Cases []struct {
			Traceparent string         `json:"traceparent"`
			ID          string         `json:"id"`
			Principal   string         `json:"principal"`
			Tenant      string         `json:"tenant"`
			Error       string         `json:"error"`
			Status      *int           `json:"status"`
			Interrupted bool           `json:"interrupted"`
			Expected    map[string]any `json:"expected"`
		} `json:"request_emission_cases"`
	}
	if err = json.Unmarshal(data, &suite); err != nil {
		t.Fatal(err)
	}
	if len(suite.Cases) == 0 {
		t.Fatal("missing cases")
	}
	for _, c := range suite.Cases {
		t.Run(c.ID, func(t *testing.T) {
			var output bytes.Buffer
			h, err := obs.NewHandler(config(), &output)
			if err != nil {
				t.Fatal(err)
			}
			defer h.Close()
			logger := slog.New(h)
			ctx, r := obs.WithRequestLogContext(obs.IncomingContext(context.Background(), headers(c.Traceparent), true))
			r.BindVerifiedIdentity(c.Principal, c.Tenant)
			if c.Error != "" {
				if err = r.SetError(c.Error); err != nil {
					t.Fatal(err)
				}
			}
			logger.InfoContext(ctx, "Application event", slog.String("principal_id", "spoofed"))
			fields, err := r.TerminalFields("POST", "/items/{id}", c.Status, 1.5, c.Interrupted)
			if err != nil {
				t.Fatal(err)
			}
			attrs := make([]slog.Attr, 0, len(fields))
			for k, v := range fields {
				attrs = append(attrs, slog.Any(k, v))
			}
			logger.LogAttrs(ctx, slog.LevelInfo, "Request finished", attrs...)
			r.Close()
			logger.InfoContext(ctx, "Outside request")
			lines := bytes.Split(bytes.TrimSpace(output.Bytes()), []byte{'\n'})
			if len(lines) != 3 {
				t.Fatalf("missing records: %+v", h.Stats())
			}
			var application, terminal, after map[string]any
			if err = json.Unmarshal(lines[0], &application); err != nil {
				t.Fatal(err)
			}
			if err = json.Unmarshal(lines[1], &terminal); err != nil {
				t.Fatal(err)
			}
			if err = json.Unmarshal(lines[2], &after); err != nil {
				t.Fatal(err)
			}
			for k, v := range c.Expected {
				if !reflect.DeepEqual(terminal[k], v) {
					t.Fatalf("field %s mismatch", k)
				}
			}
			if application["principal_id"] != c.Expected["principal_id"] {
				t.Fatal("ambient identity missing")
			}
			if _, ok := after["principal_id"]; ok {
				t.Fatal("identity survived close")
			}
			if _, ok := terminal["trace_id"]; c.Traceparent == "" && ok {
				t.Fatal("fabricated trace")
			}
			for _, row := range []map[string]any{application, terminal, after} {
				if _, ok := row["request_id"]; ok {
					t.Fatal("unexpected request identifier")
				}
			}
			if errors := obs.ValidateJSON(lines[1], "request"); len(errors) != 0 {
				t.Fatal(errors)
			}
		})
	}
}

func TestRequestEmissionEnforcesProfile(t *testing.T) {
	var output bytes.Buffer
	h, _ := obs.NewHandler(config(), &output)
	defer h.Close()
	if err := h.Handle(context.Background(), record("Missing fields", slog.String("request_event", "completed"))); err == nil {
		t.Fatal("accepted incomplete request")
	}
	ctx, r := obs.WithRequestLogContext(context.Background())
	defer r.Close()
	fields, _ := r.TerminalFields("GET", "/", nil, 1, false)
	attrs := []slog.Attr{}
	for k, v := range fields {
		attrs = append(attrs, slog.Any(k, v))
	}
	if err := h.Handle(ctx, record("No observed status", attrs...)); err == nil {
		t.Fatal("accepted unknown completed status")
	}
	if output.Len() != 0 || h.Stats().Invalid != 2 {
		t.Fatal("invalid request written")
	}
}

func TestRequestAttributionValidationAndClose(t *testing.T) {
	ctx, r := obs.WithRequestLogContext(context.Background())
	r.BindVerifiedIdentity(requestOwner, requestTenant)
	innerCtx, inner := obs.WithRequestLogContext(ctx)
	defer inner.Close()
	if obs.CurrentRequestFields(innerCtx)["principal_id"] != nil || obs.CurrentRequestFields(ctx)["principal_id"] != requestOwner {
		t.Fatal("nested identity leaked")
	}
	for _, pair := range [][2]string{{requestOwner, strings.Repeat("3", 32)}, {"username", requestTenant}, {requestOwner, strings.Repeat("0", 32)}} {
		r.BindVerifiedIdentity(pair[0], pair[1])
		if r.Fields()["principal_id"] != nil {
			t.Fatal("invalid identity accepted")
		}
	}
	if r.SetError("secret message") == nil {
		t.Fatal("invalid error code accepted")
	}
	r.Close()
	r.BindVerifiedIdentity(requestOwner, requestTenant)
	_ = r.SetError("LATE")
	if len(obs.CurrentRequestFields(ctx)) != 0 || len(r.Fields()) != 0 {
		t.Fatal("identity survived close")
	}
	if _, err := r.TerminalFields("GET", "/", nil, 1, true); err == nil {
		t.Fatal("closed receipt accepted")
	}
	if obs.CurrentRequestFields(context.Background()) != nil {
		t.Fatal("background context inherited identity")
	}
}

func TestConcurrentRequestAttribution(t *testing.T) {
	var group sync.WaitGroup
	for i := 0; i < 20; i++ {
		group.Add(1)
		go func() {
			defer group.Done()
			ctx, r := obs.WithRequestLogContext(context.Background())
			r.BindVerifiedIdentity(requestOwner, requestTenant)
			if obs.CurrentRequestFields(ctx)["principal_id"] != requestOwner {
				t.Error("missing identity")
			}
			var children sync.WaitGroup
			for j := 0; j < 5; j++ {
				children.Add(1)
				go func() {
					defer children.Done()
					r.BindVerifiedIdentity(requestOwner, requestTenant)
					_ = obs.CurrentRequestFields(ctx)
				}()
			}
			r.Close()
			children.Wait()
			if len(obs.CurrentRequestFields(ctx)) != 0 {
				t.Error("late binding leaked identity")
			}
		}()
	}
	group.Wait()
}

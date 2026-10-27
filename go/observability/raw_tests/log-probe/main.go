// log-probe emits SDK records or validates captured Go service stdout.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"

	contract "github.com/onenexus-team/onenexus-sdks/contracts/log-correlation"
	obs "github.com/onenexus-team/onenexus-sdks/go/observability"
)

func main() {
	if len(os.Args) == 2 && os.Args[1] == "emit" {
		emit()
		return
	}
	if len(os.Args) == 5 && os.Args[1] == "verify" {
		if err := verify(os.Args[2], os.Args[3], os.Args[4]); err != nil {
			fmt.Fprintln(os.Stderr, "FAIL:", err)
			os.Exit(1)
		}
		return
	}
	fmt.Fprintln(os.Stderr, "Usage: log-probe emit | verify CAPTURE.ndjson EXPECTED_TRACE EXPECTED_SERVICE")
	os.Exit(2)
}

func emit() {
	h, err := obs.NewHandler(obs.Config{Service: "go-log-probe", Environment: "development", Region: "ric1", AllowedFields: []string{"attempt"}}, os.Stdout)
	if err != nil {
		panic(err)
	}
	defer h.Close()
	logger := slog.New(h)
	ctx := obs.IncomingContext(context.Background(), http.Header{"Traceparent": {"00-11111111111111111111111111111111-2222222222222222-01"}}, true)
	logger.InfoContext(ctx, "Request accepted", slog.String("event", "request.accepted"), slog.String("outcome", "success"))
	metadata, _ := json.Marshal(obs.OutgoingHeaders(ctx))
	for attempt := 1; attempt <= 2; attempt++ {
		var saved http.Header
		_ = json.Unmarshal(metadata, &saved)
		worker := obs.IncomingContext(context.Background(), saved, true)
		logger.InfoContext(worker, "Worker attempt", slog.Int("attempt", attempt), slog.String("event", "job.attempt"), slog.String("outcome", "success"))
	}
	logger.InfoContext(obs.UncorrelatedContext(ctx), "System ready")
}

func verify(path, id, service string) error {
	f, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("capture_unavailable")
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 4096), 65536)
	count, matched := 0, 0
	for scanner.Scan() {
		count++
		line := scanner.Bytes()
		if codes := contract.ValidateJSON(line, "common"); len(codes) > 0 {
			return fmt.Errorf("line_%d_invalid:%v", count, codes)
		}
		var row struct {
			Service string `json:"service"`
			TraceID string `json:"trace_id"`
		}
		if json.Unmarshal(line, &row) != nil || row.Service != service {
			return fmt.Errorf("line_%d_service_mismatch", count)
		}
		if row.TraceID != "" {
			if row.TraceID != id {
				return fmt.Errorf("line_%d_trace_mismatch", count)
			}
			matched++
		}
	}
	if scanner.Err() != nil || matched == 0 {
		return fmt.Errorf("missing_or_unreadable_correlated_logs")
	}
	fmt.Printf("PASS: %d records; %d correlated; service=%s\n", count, matched, service)
	return nil
}

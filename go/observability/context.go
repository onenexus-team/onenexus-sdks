// Package observability provides opt-in structured logging and W3C trace context.
// It installs no global handler, tracing provider, exporter or background worker.
package observability

import (
	"context"
	"crypto/rand"
	"net/http"
	"regexp"
	"strings"

	"go.opentelemetry.io/otel/trace"
)

type contextKey struct{}
type boundary struct{ incoming trace.SpanContext }

var traceparentPattern = regexp.MustCompile(`^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$`)

// IncomingContext replaces the trace at a service/job boundary. Only headers from
// an authenticated, trusted source may be accepted. Missing, duplicate, malformed
// or untrusted context is explicitly uncorrelated; this function never mints IDs.
// Cancellation, deadlines and application values on parent are preserved.
func IncomingContext(parent context.Context, headers http.Header, trusted bool) context.Context {
	var sc trace.SpanContext
	if trusted {
		var values []string
		count := 0
		for name, v := range headers {
			if strings.EqualFold(name, "traceparent") {
				count++
				values = v
			}
		}
		if count == 1 && len(values) == 1 && len(values[0]) == 55 && traceparentPattern.MatchString(values[0]) {
			parts := strings.Split(values[0], "-")
			tid, te := trace.TraceIDFromHex(parts[1])
			sid, se := trace.SpanIDFromHex(parts[2])
			if te == nil && se == nil {
				flags := trace.TraceFlags(0)
				if strings.Contains("13579bdf", parts[3][1:]) {
					flags = trace.FlagsSampled
				}
				sc = trace.NewSpanContext(trace.SpanContextConfig{TraceID: tid, SpanID: sid, TraceFlags: flags, Remote: true})
			}
		}
	}
	// Never inherit an unrelated active trace from a previous job/request.
	active := trace.SpanContextFromContext(parent)
	if !sc.IsValid() || !active.IsValid() || active.TraceID() != sc.TraceID() || active.TraceFlags() != sc.TraceFlags() {
		parent = trace.ContextWithRemoteSpanContext(parent, sc)
	}
	return context.WithValue(parent, contextKey{}, boundary{incoming: sc})
}

// UncorrelatedContext suppresses inherited tracing at an independent work boundary.
func UncorrelatedContext(parent context.Context) context.Context {
	return IncomingContext(parent, nil, false)
}

func spanContext(ctx context.Context) trace.SpanContext {
	active := trace.SpanContextFromContext(ctx)
	if b, ok := ctx.Value(contextKey{}).(boundary); ok {
		if !b.incoming.IsValid() {
			return trace.SpanContext{}
		}
		if active.IsValid() && active.TraceID() == b.incoming.TraceID() {
			return active
		}
		return b.incoming
	}
	return active
}

// TraceID returns the current trace ID, or an empty string for uncorrelated work.
func TraceID(ctx context.Context) string {
	sc := spanContext(ctx)
	if !sc.IsValid() {
		return ""
	}
	return sc.TraceID().String()
}

// OutgoingHeaders returns only traceparent, suitable for HTTP or durable metadata.
// It never copies baggage, tracestate, credentials or application headers.
func OutgoingHeaders(ctx context.Context) http.Header {
	h := make(http.Header)
	sc := spanContext(ctx)
	if sc.IsValid() {
		flags := "00"
		if sc.IsSampled() {
			flags = "01"
		}
		h.Set("traceparent", "00-"+sc.TraceID().String()+"-"+sc.SpanID().String()+"-"+flags)
	}
	return h
}

// EdgeContext is ONLY for an explicitly designated edge and shared edge-policy
// tests. OneNexus business services use IncomingContext; Envoy owns ID creation.
// Edge policy is unsampled. No spans are started or exported here.
func EdgeContext(parent context.Context, headers http.Header, trusted bool) context.Context {
	ctx := IncomingContext(parent, headers, trusted)
	sc := spanContext(ctx)
	if sc.IsValid() {
		sc = sc.WithTraceFlags(0)
	} else {
		var tid trace.TraceID
		var sid trace.SpanID
		for !tid.IsValid() {
			_, _ = rand.Read(tid[:])
		}
		for !sid.IsValid() {
			_, _ = rand.Read(sid[:])
		}
		sc = trace.NewSpanContext(trace.SpanContextConfig{TraceID: tid, SpanID: sid})
	}
	return context.WithValue(trace.ContextWithSpanContext(parent, sc), contextKey{}, boundary{incoming: sc})
}

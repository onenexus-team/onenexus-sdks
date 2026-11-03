package observability

import (
	"context"
	"errors"
	"regexp"
	"sync"
)

var requestFieldNames = []string{"request_id", "principal_id", "tenant_id", "error_code", "request_event", "http.request.method", "http.route", "http.response.status_code", "duration_ms"}
var requestIDPattern = regexp.MustCompile(`^[A-Za-z0-9._:-]{1,128}$`)
var tenantPattern = regexp.MustCompile(`^[0-9a-f]{32}$`)
var principalPattern = regexp.MustCompile(`^nx1://[A-Za-z0-9._:-]+/([0-9a-f]{32})/[A-Za-z0-9._:-]+/[A-Za-z0-9._:-]+/(User|ServiceClient|Workload)/[A-Za-z0-9._:-]+$`)

type requestContextKey struct{}

// RequestLogContext is diagnostic attribution, never an authorization credential.
// Close it at the HTTP boundary so detached goroutines cannot retain attribution.
type RequestLogContext struct {
	mu     sync.Mutex
	closed bool
	values map[string]any
}

func WithRequestLogContext(ctx context.Context, requestID string) (context.Context, *RequestLogContext, error) {
	if !requestIDPattern.MatchString(requestID) {
		return ctx, nil, errors.New("invalid_request_id")
	}
	receipt := &RequestLogContext{values: map[string]any{"request_id": requestID, "principal_id": nil, "tenant_id": nil}}
	return context.WithValue(ctx, requestContextKey{}, receipt), receipt, nil
}

// BindVerifiedIdentity must only follow credential verification, before policy/quota checks.
// Empty principal supports legacy keys with a known tenant but no canonical owner.
func (r *RequestLogContext) BindVerifiedIdentity(principalID, tenantID string) {
	var tenant, principal any
	if tenantPattern.MatchString(tenantID) && tenantID != "00000000000000000000000000000000" {
		tenant = tenantID
	}
	if len(principalID) <= 1024 {
		match := principalPattern.FindStringSubmatch(principalID)
		if len(match) > 1 && tenant != nil && match[1] == tenantID {
			principal = principalID
		}
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if !r.closed {
		r.values["principal_id"], r.values["tenant_id"] = principal, tenant
	}
}

func (r *RequestLogContext) SetError(code string) error {
	if !requestIDPattern.MatchString(code) {
		return errors.New("invalid_error_code")
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if !r.closed {
		r.values["error_code"] = code
	}
	return nil
}

func (r *RequestLogContext) Fields() map[string]any {
	r.mu.Lock()
	defer r.mu.Unlock()
	result := make(map[string]any, len(r.values))
	for k, v := range r.values {
		result[k] = v
	}
	return result
}

// TerminalFields expects a route template and actual observed response status.
// Pass nil before headers; preserve 200 when streaming is interrupted after headers.
func (r *RequestLogContext) TerminalFields(method, route string, status *int, durationMS float64, interrupted bool) (map[string]any, error) {
	result := r.Fields()
	if len(result) == 0 {
		return nil, errors.New("request_context_closed")
	}
	result["request_event"] = "completed"
	if interrupted {
		result["request_event"] = "interrupted"
	}
	result["http.request.method"], result["http.route"] = method, route
	result["http.response.status_code"] = nil
	if status != nil {
		result["http.response.status_code"] = *status
	}
	result["duration_ms"] = durationMS
	if _, ok := result["error_code"]; !ok {
		result["error_code"] = nil
		if status != nil && *status >= 400 {
			result["error_code"] = "UNCLASSIFIED"
		}
	}
	return result, nil
}

func (r *RequestLogContext) Close() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.closed = true
	clear(r.values)
}

func CurrentRequestFields(ctx context.Context) map[string]any {
	if receipt, ok := ctx.Value(requestContextKey{}).(*RequestLogContext); ok {
		return receipt.Fields()
	}
	return nil
}

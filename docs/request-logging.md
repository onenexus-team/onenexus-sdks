# Shared HTTP request logging

The observability packages provide a `request` record profile and request-local
attribution helpers for Python, TypeScript, Go and .NET. This is an additive SDK
change. Existing common/correlated/lifecycle records keep their existing rules;
services adopt the request profile explicitly through `request_event`.

## Contract

Every terminal HTTP record includes the normal common log fields and these fields:

| Field | Meaning |
| --- | --- |
| `request_event` | `completed` or `interrupted`; identifies terminal HTTP records. |
| `principal_id` | Verified canonical `nx1://` User, ServiceClient or Workload subject; otherwise JSON null. |
| `tenant_id` | Verified tenant as 32 lowercase UUID hex digits, excluding the zero UUID; otherwise JSON null. |
| `http.request.method` | Uppercase HTTP method, at most 32 letters. |
| `http.route` | Registered route template, at most 512 printable ASCII characters. Use `_unmatched` when unavailable. Never use raw URLs or query strings. |
| `http.response.status_code` | Observed HTTP status, 100–599. Null is permitted only for an interrupted request before response headers. |
| `duration_ms` | Finite, nonnegative elapsed milliseconds. |
| `error_code` | Bounded machine code, at most 128 ASCII letters/digits or `._:-`. The helper uses `UNCLASSIFIED` for an HTTP error without a supplied code. Otherwise null is permitted. |

`trace_id` is the sole identifier for correlation and counting. It comes from the
existing trusted correlation context. Request helpers accept no identifier argument
and do not create, populate or require `request_id`. The request helper
does not create a trace, trust an inbound header, or borrow an unrelated framework
span. Missing trusted correlation does not suppress the terminal request record.
The gateway remains responsible for creating and propagating canonical traces.
No `auth_state` or `principal_type` fields are introduced.

Each logger automatically selects the stricter request profile whenever
`request_event` is present. Missing fields, completed requests with unknown status,
and HTTP errors with a null error code are rejected using the existing invalid/drop
counter behavior. No per-service custom-field allowlist is needed for these fields.
The new profile does not change the legacy exported base-format version constants;
the SDK release version identifies availability of these APIs.

## Ownership and lifecycle

1. HTTP middleware creates an attribution context without a separate identifier. It also
   binds the existing SDK correlation context using the service's trusted-ingress
   policy. Authentication remains outside the logging SDK.
2. After credential verification, the service calls `bind_verified_identity` /
   `bindVerifiedIdentity` / `BindVerifiedIdentity`, before policy or quota checks.
   JWT consumers use verified claims. API-key consumers use the verified key's
   trusted owner and tenant context. Never derive a principal from a username,
   caller-supplied identity header, or an unverified token.
3. Canonical subject and tenant must match. Malformed/mismatched subjects become
   null; a verified tenant can remain known for a legacy key without an owner.
   The helper validates attribution shape, not credential authenticity. Its values
   must never become authorization inputs or outbound identity headers.
4. Application logs inside the active request inherit verified identity and the existing trace context.
   Ambient attribution takes precedence over explicit log-field values. Capture
   stable error codes at the error mapping boundary; do not pass exception text.
5. The response middleware emits one terminal record using `terminal_fields` /
   `terminalFields` / `TerminalFields`. Observe the response actually sent: an
   interrupted 200 stream stays 200, and a disconnect before headers has null status.
   Do not synthesize 499 or 500 from an exception or cancellation alone.
6. Close/dispose in every finish, close, exception, cancellation and health-check
   path. Closing clears shared state, including references inherited by detached
   tasks, and prevents late identity rebinding. Context snapshots are for immediate
   logging, not durable job metadata. Start a separate scope for independent work.

Python's `request_log_context()` context manager closes automatically.
TypeScript uses `new RequestLogContext()` and `withRequestLogContext(receipt, fn)`;
the HTTP finish/close fence must call `receipt.close()` because callback middleware
can return before a response finishes. Go uses `WithRequestLogContext(ctx)` and
`defer receipt.Close()`; pass the returned context to `slog` calls. .NET uses
`using var receipt = RequestLogContext.Begin()` and disposes scopes in order.

Response headers, browser CORS exposure, and error-body trace IDs are service
integration work. Consumers return the canonical `X-Trace-ID`
when available, expose it through CORS, and add trace IDs to their standard
application error bodies. Do not wrap protocol-defined OAuth responses merely to
change their body shape.

## Counting and release

Loki dashboards select terminal records using `request_event`, parse
`http.response.status_code` as the `http_status` query alias, and filter 400–599.
Count distinct nonempty `trace_id` values within the selected time window. Repeated
logs and service hops for the same trace must not increase the overall trace count.
For a breakdown, deduplicate by (`error_code`, `trace_id`), optionally scoped to a
service. A trace can appear under multiple error codes, so adding the groups is not
a globally distinct trace total. Policy decisions are excluded from terminal HTTP
counts. These are failed-trace counts, not counts of independent HTTP attempts.

Records without a trusted trace remain diagnostic logs and are excluded from
distinct-trace counts; monitor them separately as missing correlation. Keep trace,
principal and tenant IDs as JSON fields rather than indexed Loki labels.
Gateway-generated failures require gateway access logs as well.

The shared vectors in `tests/logging/scenarios.json` cover schema validation and
real logger emissions in all four packages. Tests also cover concurrent contexts,
nested scopes, invalid attribution, terminal validation, and late binding after
close. Run the source and installed-artifact checks in [logging.md](logging.md).

Merge the SDK PR and publish a new coordinated SDK release through the existing
release pipeline. Verify all four artifacts before upgrading consumer pins and
lockfiles in the monorepo. Services must adopt the new context/terminal helpers;
a package version bump alone does not resolve identity or observe responses.
Live gateway → service → Loki checks belong to the monorepo rollout and are not
proven by package tests.

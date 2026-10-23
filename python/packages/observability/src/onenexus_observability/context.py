"""W3C context only: no SDK/provider registration, recording or exporter."""

from __future__ import annotations

import secrets
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from opentelemetry import context, trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_PROPAGATOR = TraceContextTextMapPropagator()


def incoming_context(
    headers: Mapping[str, str], *, trusted: bool, preserve_sampling: bool = True
) -> context.Context:
    """Use only at a new boundary. Trust comes from service policy, not a header.

    Never call this over an existing instrumented request span. Inside such a
    request, current_trace_id/outgoing_headers already use that active span.
    Baggage/tracestate are deliberately excluded from this correlation API.
    """
    values = [v for k, v in headers.items() if k.lower() == "traceparent"]
    if trusted and len(values) == 1 and isinstance(values[0], str) and len(values[0]) <= 512:
        extracted = _PROPAGATOR.extract({"traceparent": values[0]}, context=context.Context())
        parent = trace.get_current_span(extracted).get_span_context()
        if parent.is_valid:
            if preserve_sampling:
                return extracted
            return trace.set_span_in_context(
                NonRecordingSpan(
                    SpanContext(
                        trace_id=parent.trace_id,
                        span_id=parent.span_id,
                        is_remote=True,
                        trace_flags=TraceFlags(0),
                    )
                ),
                context.Context(),
            )
    return trace.set_span_in_context(
        NonRecordingSpan(
            SpanContext(
                trace_id=secrets.randbits(128) or 1,
                span_id=secrets.randbits(64) or 1,
                is_remote=False,
                trace_flags=TraceFlags(0),
            )
        ),
        context.Context(),
    )


@contextmanager
def bound_context(value: context.Context) -> Iterator[None]:
    token = context.attach(value)
    try:
        yield
    finally:
        context.detach(token)


def current_trace_id() -> str | None:
    value = trace.get_current_span().get_span_context()
    return f"{value.trace_id:032x}" if value.is_valid else None


def outgoing_headers() -> dict[str, str]:
    """Capture context now for HTTP or durable metadata. Never returns baggage."""
    headers: dict[str, str] = {}
    _PROPAGATOR.inject(headers)
    return {"traceparent": headers["traceparent"]} if "traceparent" in headers else {}

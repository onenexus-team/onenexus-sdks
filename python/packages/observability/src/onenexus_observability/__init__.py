"""Shared contract-backed logging primitives. Initialization is explicit."""

from .context import bound_context, current_trace_id, incoming_context, outgoing_headers
from .contract import (
    CONTRACT_DIGEST,
    CONTRACT_VERSION,
    ContractViolation,
    check_allowed_fields,
    validate_record,
)
from .drop_metric import (
    DropCount,
    DropReason,
    LogDropCounter,
    drop_metrics_text,
    log_drop_counts,
    register_drop_metric,
)
from .logging import JsonLogHandler, LogConfig, build_record, error_fingerprint, install_handler
from .request import RequestLogContext, current_request_fields, request_log_context

__all__ = [
    "CONTRACT_DIGEST",
    "CONTRACT_VERSION",
    "ContractViolation",
    "DropCount",
    "DropReason",
    "JsonLogHandler",
    "LogConfig",
    "bound_context",
    "build_record",
    "check_allowed_fields",
    "current_trace_id",
    "error_fingerprint",
    "LogDropCounter",
    "drop_metrics_text",
    "incoming_context",
    "install_handler",
    "log_drop_counts",
    "outgoing_headers",
    "register_drop_metric",
    "validate_record",
    "RequestLogContext",
    "current_request_fields",
    "request_log_context",
]

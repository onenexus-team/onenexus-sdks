"""Shared contract-backed logging primitives. Initialization is explicit."""

from .context import bound_context, current_trace_id, incoming_context, outgoing_headers
from .contract import CONTRACT_DIGEST, CONTRACT_VERSION, ContractViolation, validate_record
from .logging import JsonLogHandler, LogConfig, build_record, install_handler

__all__ = [
    "CONTRACT_DIGEST",
    "CONTRACT_VERSION",
    "ContractViolation",
    "JsonLogHandler",
    "LogConfig",
    "bound_context",
    "build_record",
    "current_trace_id",
    "incoming_context",
    "install_handler",
    "outgoing_headers",
    "validate_record",
]

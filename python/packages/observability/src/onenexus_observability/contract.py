"""Validation rules bundled with the logger. No separate contract dependency."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Collection
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from importlib.resources import files

# Log-format identity, not the package version.
CONTRACT_VERSION = "0.6.0"
# sha256 of the bundled schema.json; equal in every language (tests/logging).
CONTRACT_DIGEST = "b0703638c41630885ad82f6db201a84e04545912bd4aaf1035e995e08aeda40b"
_SCHEMA = json.loads(files("onenexus_observability").joinpath("schema.json").read_bytes())
_VALIDATORS = {
    name: Draft202012Validator({"$defs": _SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})
    for name in _SCHEMA["$defs"]
}
MAX_MESSAGE_BYTES = _SCHEMA["x-semantic-checks"]["message_max_utf8_bytes"]
MAX_RECORD_BYTES = _SCHEMA["x-semantic-checks"]["record_max_compact_utf8_bytes"]
MAX_FIELD_BYTES = _SCHEMA["x-semantic-checks"]["field_max_utf8_bytes"]
MAX_STACKTRACE_BYTES = _SCHEMA["x-semantic-checks"]["stacktrace_max_utf8_bytes"]
_COMMON = _SCHEMA["$defs"]["common"]["properties"]
MAX_DROPPED_FIELD_COUNT = _COMMON["logging.dropped_field_count"]["maximum"]
MAX_ERROR_TYPE_CHARS = _COMMON["error.type"]["maxLength"]
# Logger-owned fields stay protected when optional shared fields are added.
COMMON_FIELDS = frozenset(_SCHEMA["x-protected-fields"])

# The field registry (design review E1): which custom names a service may allow.
_REGISTRY = _SCHEMA["x-field-registry"]
MAX_CUSTOM_FIELDS = _REGISTRY["max_custom_fields"]
_NAME_PATTERN = re.compile(_REGISTRY["name_pattern"])
_NAME_MAX_CHARS = _REGISTRY["name_max_chars"]
_NAMESPACES = frozenset(_REGISTRY["namespaces"])
_RESERVED_NAMESPACES = frozenset(_REGISTRY["reserved_namespaces"])
# One check per registry value type; a type missing here fails at import.
_VALUE_TYPES: dict[str, Callable[[object], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}
_FIELD_TYPES = {name: _VALUE_TYPES[field["type"]] for name, field in _REGISTRY["fields"].items()}
_SCALAR_CHECKS = tuple(_VALUE_TYPES[name] for name in _REGISTRY["value_types"])


def _registry_error(rule: str, detail: object) -> ValueError:
    return ValueError(f"invalid_allowed_fields: {rule}: {detail}")


def check_allowed_fields(names: Collection[str]) -> None:
    """Raise ``ValueError("invalid_allowed_fields: <rule>: <detail>")`` at the first rejected name.

    Rules, in order: protected, format, registered field (accepted),
    reserved namespace, namespace.
    More than ``MAX_CUSTOM_FIELDS`` names fails as ``too_many``.
    """
    if len(names) > MAX_CUSTOM_FIELDS:
        raise _registry_error("too_many", f"{len(names)} > {MAX_CUSTOM_FIELDS}")
    for name in names:
        if name in COMMON_FIELDS:
            raise _registry_error("protected", name)
        if not isinstance(name, str) or len(name) > _NAME_MAX_CHARS or not _NAME_PATTERN.fullmatch(name):
            raise _registry_error("format", name)
        if name in _FIELD_TYPES:
            continue
        head, _, rest = name.partition(".")
        if head in _RESERVED_NAMESPACES:
            raise _registry_error("reserved", name)
        if not rest or head not in _NAMESPACES:
            raise _registry_error("namespace", name)


def valid_field_value(name: str, value: object) -> bool:
    """A flat scalar (string, finite number, boolean, null) of the field's registered type, if any."""
    if not any(check(value) for check in _SCALAR_CHECKS):
        return False
    return value is None or name not in _FIELD_TYPES or _FIELD_TYPES[name](value)


def _code(field: object) -> str:
    return {"message": "missing_or_invalid_message", "trace_id": "missing_or_invalid_trace_id"}.get(
        str(field), "schema_invalid"
    )


def validate_record(record: object, profile: str = "common") -> list[str]:
    """Stable codes only. The schema supplies constraints; semantic limits are explicit."""
    if profile not in _VALIDATORS:
        return ["unknown_profile"]
    errors: set[str] = set()
    try:
        for error in _VALIDATORS[profile].iter_errors(record):
            if error.validator == "required" and isinstance(record, dict):
                errors.update(_code(k) for k in error.validator_value if k not in record)
            else:
                errors.add(_code(next(iter(error.path), None)))
        if isinstance(record, dict):
            # Preserve strict integer semantics (JSON Schema also accepts 1.0).
            if type(record.get("timestamp")) is not int:
                errors.add("schema_invalid")
            message = record.get("message")
            if isinstance(message, str) and len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
                errors.add("missing_or_invalid_message")
            size = 0
            for chunk in json.JSONEncoder(
                ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).iterencode(record):
                size += len(chunk.encode("utf-8"))
                if size > MAX_RECORD_BYTES:
                    errors.add("record_too_large")
                    # Continue to detect invalid JSON too, as required by the contract.
    except (TypeError, ValueError, UnicodeError, RecursionError):
        errors.add("invalid_json_record")
    return sorted(errors)


class ContractViolation(ValueError):
    def __init__(self, codes: list[str]) -> None:
        self.codes = tuple(codes)
        super().__init__(",".join(codes))


def encode_record(record: dict[str, Any], profile: str = "common") -> str:
    errors = validate_record(record, profile)
    if errors:
        raise ContractViolation(errors)
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

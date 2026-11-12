"""Validation rules bundled with the logger. No separate contract dependency."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from importlib.resources import files

# Log-format identity, not the package version.
CONTRACT_VERSION = "0.5.0"
# sha256 of the bundled schema.json; equal in every language (tests/logging).
CONTRACT_DIGEST = "3910951d0ea07dcce757bef9a88ff841bd6015d6b3bb1437678ca4bd041b438c"
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

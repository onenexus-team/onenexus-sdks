"""Read the pinned release, never fetch or generate a schema at runtime."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

CONTRACT_VERSION = "0.3.1"
CONTRACT_DIGEST = "9be133120a0fc9baf286110131f70c9dc193ed14957f9461d431ca159b798538"
ARCHIVE_DIGEST = "752a95f6986359c604b35c99a19de943459dfcf8ab22a9916060818e07a4c21b"


def _load() -> dict[str, Any]:
    root = files("onenexus_observability").joinpath("_contract")
    manifest = json.loads(root.joinpath("manifest.json").read_bytes())
    digest = hashlib.sha256()
    data: dict[str, bytes] = {}
    if manifest["version"] != CONTRACT_VERSION or [x["path"] for x in manifest["files"]] != [
        "schema.json",
        "vectors.json",
    ]:
        raise ValueError("contract_identity_mismatch")
    for item in manifest["files"]:
        name = item["path"]
        data[name] = root.joinpath(name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest() != item["sha256"]:
            raise ValueError("contract_integrity_failed")
        digest.update(name.encode() + b"\0" + data[name])
    if digest.hexdigest() != CONTRACT_DIGEST or manifest["sha256"] != CONTRACT_DIGEST:
        raise ValueError("contract_integrity_failed")
    schema: dict[str, Any] = json.loads(data["schema.json"])
    if schema["x-contract-version"] != CONTRACT_VERSION:
        raise ValueError("contract_identity_mismatch")
    return schema


_SCHEMA = _load()
_VALIDATORS = {
    name: Draft202012Validator(definition) for name, definition in _SCHEMA["$defs"].items()
}
MAX_MESSAGE_BYTES = _SCHEMA["x-semantic-checks"]["message_max_utf8_bytes"]
MAX_RECORD_BYTES = _SCHEMA["x-semantic-checks"]["record_max_compact_utf8_bytes"]
COMMON_FIELDS = frozenset(_SCHEMA["$defs"]["common"]["properties"])


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

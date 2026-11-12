"""Error fingerprint (tests/logging/scenarios.json `error_fingerprint`, design review F1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from onenexus_observability import LogConfig, build_record, error_fingerprint, validate_record

ROOT = Path(__file__).resolve().parents[4]
SPEC = json.loads((ROOT / "tests/logging/scenarios.json").read_text())["error_fingerprint"]
FIELD = SPEC["field"]
CONFIG = LogConfig("svc", "development", "region-1", frozenset({"shared.note"}))
# The shared degradation allowlist: a caller may supply the stack.
STACK_CONFIG = LogConfig(
    "svc", "development", "region-1", frozenset({"shared.note", "exception.stacktrace"})
)


def _exc_info():
    try:
        raise ValueError("private-sentinel")
    except ValueError:
        return sys.exc_info()


@pytest.mark.parametrize("case", SPEC["cases"], ids=[c["id"] for c in SPEC["cases"]])
def test_vectors(case):
    # type_only, frames, line_numbers_ignored, frame_without_file,
    # type_changes_fingerprint, multibyte
    assert error_fingerprint(case["error_type"], case["stacktrace"]) == case["fingerprint"]


def test_logged_error_has_fingerprint():
    record = build_record(CONFIG, "Job failed", level="ERROR", exc_info=_exc_info())
    assert record[FIELD] == error_fingerprint(record["error.type"], record.get("exception.stacktrace"))
    assert "private-sentinel" not in json.dumps(record)
    assert validate_record(record, "common") == []


def test_same_error_same_fingerprint():
    first, second = (
        build_record(CONFIG, "Job failed", level="ERROR", exc_info=_exc_info()) for _ in range(2)
    )
    assert first[FIELD] == second[FIELD]


def test_stable_when_fitted():
    info = _exc_info()
    plain = build_record(CONFIG, "Job failed", level="ERROR", exc_info=info)
    long_stack = "\n".join(f"at function_{i} (deep_module.py:{i})" for i in range(55))
    assert len(long_stack.encode()) < 2048  # whole: only fitting can shorten it
    fields = {"exception.stacktrace": long_stack, "shared.note": "n" * 1000}
    big = build_record(STACK_CONFIG, "x" * 1000, level="ERROR", fields=fields, exc_info=info)
    assert big["exception.stacktrace"] != long_stack  # the record was fitted
    assert big["logging.truncated"] is True
    assert big[FIELD] == error_fingerprint(plain["error.type"], long_stack)


def test_caller_value_removed():
    record = build_record(
        CONFIG, "Job failed", level="ERROR", fields={FIELD: "0000000000000000"}, exc_info=_exc_info()
    )
    assert record[FIELD] != "0000000000000000"
    assert record["logging.dropped_field_count"] == 1


def test_no_error_no_fingerprint():
    assert FIELD not in build_record(CONFIG, "Job done")

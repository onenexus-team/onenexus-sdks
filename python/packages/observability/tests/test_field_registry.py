"""One field registry (tests/logging/scenarios.json `field_registry`, design review E1).

One test per shared case; each test name is the case id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from onenexus_observability import LogConfig, build_record, check_allowed_fields
from onenexus_observability.contract import MAX_CUSTOM_FIELDS

ROOT = Path(__file__).resolve().parents[4]
SPEC = json.loads((ROOT / "tests/logging/scenarios.json").read_text())["field_registry"]
CONFIG_CASES = {case["id"]: case for case in SPEC["config_cases"]}
VALUE_CASES = {case["id"]: case for case in SPEC["value_cases"]}
VALUE_CONFIG = LogConfig("registry-test", "development", "region-1", frozenset(SPEC["value_allowed_fields"]))


def expand(names: list[str] | dict[str, object]) -> list[str]:
    """scenarios.json `names_expansion`."""
    if isinstance(names, list):
        return names
    prefix, count = str(names["prefix"]), int(str(names["count"]))
    if "repeat" in names:
        return [prefix + str(names["repeat"]) * count]
    return [f"{prefix}{i}" for i in range(count)]


def check_config_case(case_id: str) -> None:
    case = CONFIG_CASES[case_id]
    names = expand(case["names"])
    if case["accepted"]:
        check_allowed_fields(names)
        assert LogConfig("registry-test", "development", "region-1", frozenset(names)).allowed_fields == set(names)
        return
    # The detail names the rule and the field (for too_many, the count).
    expected = f"{SPEC['config_error']}: {case['reason']}: "
    if case["reason"] == "too_many":
        expected += f"{len(names)} > {MAX_CUSTOM_FIELDS}"
    else:
        expected += names[0]
    for check in (
        lambda: check_allowed_fields(names),
        lambda: LogConfig("registry-test", "development", "region-1", frozenset(names)),
    ):
        with pytest.raises(ValueError) as error:
            check()
        assert str(error.value) == expected


def check_value_case(case_id: str) -> None:
    case = VALUE_CASES[case_id]
    record = build_record(VALUE_CONFIG, "Registry value", fields=case["fields"])
    assert sorted(name for name in case["fields"] if name in record) == case["kept"]
    assert record.get("logging.dropped_field_count") == case["dropped_field_count"]
    for name in case["kept"]:
        assert record[name] == case["fields"][name]


def test_accepts_service_namespace():
    check_config_case("accepts_service_namespace")


def test_accepts_registered_field():
    check_config_case("accepts_registered_field")


def test_accepts_otel_namespace():
    check_config_case("accepts_otel_namespace")


def test_accepts_registered_in_reserved():
    check_config_case("accepts_registered_in_reserved")


def test_accepts_max_custom_fields():
    check_config_case("accepts_max_custom_fields")


def test_rejects_protected():
    check_config_case("rejects_protected")


def test_rejects_bad_format():
    check_config_case("rejects_bad_format")


def test_rejects_too_many_segments():
    check_config_case("rejects_too_many_segments")


def test_rejects_too_long():
    check_config_case("rejects_too_long")


def test_rejects_reserved_namespace():
    check_config_case("rejects_reserved_namespace")


def test_rejects_unregistered_flat():
    check_config_case("rejects_unregistered_flat")


def test_rejects_unregistered_namespace():
    check_config_case("rejects_unregistered_namespace")


def test_rejects_too_many():
    check_config_case("rejects_too_many")


def test_scalar_values_kept():
    check_value_case("scalar_values_kept")


def test_object_value_removed():
    check_value_case("object_value_removed")


def test_array_value_removed():
    check_value_case("array_value_removed")


def test_registered_type_enforced():
    check_value_case("registered_type_enforced")


def test_registered_type_accepted():
    check_value_case("registered_type_accepted")


def test_every_python_case_has_a_test():
    module = sys.modules[__name__]
    for case in SPEC["config_cases"] + SPEC["value_cases"]:
        if "python" in case["languages"]:
            assert callable(getattr(module, f"test_{case['id']}", None)), case["id"]


def test_a_name_that_is_not_a_string_is_a_format_error():
    with pytest.raises(ValueError, match=r"^invalid_allowed_fields: format: "):
        check_allowed_fields([1])  # type: ignore[list-item]


def test_allowed_fields_must_be_a_frozenset():
    with pytest.raises(ValueError, match=r"^invalid_allowed_fields: "):
        LogConfig("registry-test", "development", "region-1", {"example.s"})  # type: ignore[arg-type]


def test_a_tuple_and_a_non_json_value_are_removed():
    record = build_record(
        VALUE_CONFIG, "Registry value", fields={"example.a": (1, 2), "example.o": object(), "example.s": "x"}
    )
    assert "example.a" not in record and "example.o" not in record and record["example.s"] == "x"
    assert record["logging.dropped_field_count"] == 2

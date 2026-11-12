import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from check_results import BehaviorMismatch as Mismatch, check_results

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = Path(__file__).with_name("scenarios.json")


class SharedTests(unittest.TestCase):
    def setUp(self):
        self.suite = json.loads(SCENARIOS.read_text())
        self.result = {"results": []}
        for c in self.suite["record_cases"]:
            self.result["results"].append(
                {"kind": "record", "id": c["id"], "errors": c["errors"]}
            )
        for i, c in enumerate(self.suite["context_cases"]):
            trace = (
                c["traceparent"].split("-")[1]
                if c["preserve_trace"]
                else f"{i + 1:032x}"
            )
            self.result["results"].append(
                {
                    "kind": "context",
                    "id": c["id"],
                    "trace_id": trace,
                    "outgoing_traceparent": f"00-{trace}-2222222222222222-00",
                    "after_trace_id": None,
                }
            )

    def check(self, value):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "observed.json"
            path.write_text(json.dumps(value))
            return check_results(path)

    def test_complete_expected_observations(self):
        self.assertEqual(self.check(self.result), len(self.result["results"]))

    def test_rejects_incomplete_duplicate_and_unknown_cases(self):
        for change in ("missing", "duplicate", "unknown"):
            result = copy.deepcopy(self.result)
            if change == "missing":
                result["results"].pop()
            elif change == "duplicate":
                result["results"][0] = result["results"][1]
            else:
                result["results"][0]["id"] = "unknown"
            with self.assertRaises(Mismatch):
                self.check(result)

    def test_rejects_wrong_validation_and_context_leaks(self):
        for key, value in [
            ("errors", []),
            ("after_trace_id", "1" * 32),
            ("trace_id", "0" * 32),
            ("outgoing_traceparent", "bad"),
        ]:
            result = copy.deepcopy(self.result)
            row = (
                next(c for c in result["results"] if c.get("errors"))
                if key == "errors"
                else result["results"][-1]
            )
            row[key] = value
            with self.assertRaises(Mismatch):
                self.check(result)

    def test_language_rules_remain_equivalent(self):
        paths = [
            "python/packages/observability/src/onenexus_observability/schema.json",
            "ts/packages/observability/src/schema.json",
            "go/packages/observability/schema.json",
            "dotnet/packages/observability/src/schema.json",
        ]
        definitions = [json.loads((ROOT / path).read_text()) for path in paths]
        definition = definitions[0]
        for path, other in zip(paths[1:], definitions[1:]):
            self.assertEqual(definition, other, path)
        self.assertIn("environment", definition["$defs"]["common"]["required"])
        self.assertTrue(self.suite["emission_cases"])
        self.assertTrue(self.suite["request_emission_cases"])
        self.assertIn("request", definition["$defs"])

    def test_degradation_cases_cover_every_rule(self):
        cases = {c["id"]: c for c in self.suite["degradation_cases"]}
        self.assertEqual(len(cases), len(self.suite["degradation_cases"]))
        expects = [c["expect"] for c in cases.values()]
        self.assertTrue(any(e["truncated"] for e in expects))
        self.assertTrue(any(e["dropped_field_count"] for e in expects))
        self.assertTrue(any(e.get("error_type") for e in expects))
        self.assertTrue(any("record_max_bytes" in e for e in expects))
        languages = {"python", "typescript", "go", "dotnet"}
        self.assertEqual(set(self.suite["degradation_error_type"]), languages)
        schema = json.loads(
            (ROOT / "go/packages/observability/schema.json").read_text()
        )
        protected = set(schema["x-protected-fields"])
        self.assertTrue({"logging.truncated", "logging.dropped_field_count"} <= protected)
        # Callers (e.g. MLOps) may still set their own error fields.
        self.assertFalse({"error.type", "exception.stacktrace"} & protected)

    def test_every_language_tests_every_write_model_case(self):
        model = self.suite["write_model"]
        self.assertEqual((model["queue_capacity"], model["close_timeout_ms"]), (1024, 2000))
        self.assertEqual(model["error_wait_ms"], 50)
        test_files = {
            "python": "python/packages/observability/tests/test_write_model.py",
            "typescript": "ts/packages/observability/test/write-model.test.ts",
            "go": "go/packages/observability/tests/write_model_test.go",
            "dotnet": "dotnet/packages/observability/tests/unit/WriteModelTests.cs",
        }
        for case in model["cases"]:
            for language in case["languages"]:
                text = (ROOT / test_files[language]).read_text()
                with self.subTest(case=case["id"], language=language):
                    self.assertIn(case["id"], text)

    def test_every_language_tests_every_drop_metric_case(self):
        metric = self.suite["drop_metric"]
        self.assertEqual(metric["otel_name"], "onenexus.log.records.dropped")
        self.assertEqual(metric["prometheus_name"], "onenexus_log_records_dropped_total")
        # The reasons are exactly the write-model counters that mean "not written".
        not_written = set(self.suite["write_model"]["counters"]) - {"written", "pending"}
        self.assertEqual(metric["reasons"], sorted(not_written))
        test_files = {
            "python": "python/packages/observability/tests/test_drop_metric.py",
            "typescript": "ts/packages/observability/test/drop-metric.test.ts",
            "go": "go/packages/observability/tests/drop_metric_test.go",
            "dotnet": "dotnet/packages/observability/tests/unit/DropMetricTests.cs",
        }
        for case in metric["cases"]:
            for language in case["languages"]:
                text = (ROOT / test_files[language]).read_text()
                with self.subTest(case=case["id"], language=language):
                    self.assertIn(case["id"], text)

    def test_contract_digest_is_the_schema_hash_in_every_language(self):
        schema = ROOT / "go/packages/observability/schema.json"
        digest = hashlib.sha256(schema.read_bytes()).hexdigest()
        for path, pattern in [
            ("python/packages/observability/src/onenexus_observability/contract.py", r'CONTRACT_DIGEST = "([0-9a-f]{64})"'),
            ("ts/packages/observability/src/rules.ts", r'CONTRACT_DIGEST = "([0-9a-f]{64})"'),
            ("dotnet/packages/observability/src/Contract.cs", r'Digest = "([0-9a-f]{64})"'),
        ]:
            found = re.search(pattern, (ROOT / path).read_text())
            self.assertIsNotNone(found, path)
            self.assertEqual(found.group(1), digest, path)

    def test_no_standalone_contract_distribution_remains(self):
        for path in [
            "contracts/log-correlation",
            "ts/packages/log-contract",
            "dotnet/src/OneNexus.LogContract",
            ".github/workflows/log-contract-release.yml",
        ]:
            self.assertFalse((ROOT / path).exists(), path)


SCHEMA = ROOT / "go/packages/observability/schema.json"
FIELD_REGISTRY_TESTS = {
    "python": "python/packages/observability/tests/test_field_registry.py",
    "typescript": "ts/packages/observability/test/field-registry.test.ts",
    "go": "go/packages/observability/tests/field_registry_test.go",
    "dotnet": "dotnet/packages/observability/tests/unit/FieldRegistryTests.cs",
}


def expand_names(names):
    if isinstance(names, list):
        return names
    if "repeat" in names:
        return [names["prefix"] + names["repeat"] * names["count"]]
    return [f"{names['prefix']}{i}" for i in range(names["count"])]


def registry_reason(registry, protected, names):
    """The reference check: the first failing rule, in check_order, or None."""
    if len(names) > registry["max_custom_fields"]:
        return "too_many"
    pattern = re.compile(registry["name_pattern"])
    for name in names:
        if name in protected:
            return "protected"
        if len(name) > registry["name_max_chars"] or not pattern.fullmatch(name):
            return "format"
        if name in registry["fields"]:
            continue
        head, _, rest = name.partition(".")
        if head in registry["reserved_namespaces"]:
            return "reserved"
        if not rest or head not in registry["namespaces"]:
            return "namespace"
    return None


class FieldRegistryTests(unittest.TestCase):
    def setUp(self):
        schema = json.loads(SCHEMA.read_text())
        self.registry = schema["x-field-registry"]
        self.protected = set(schema["x-protected-fields"])
        self.spec = json.loads(SCENARIOS.read_text())["field_registry"]

    def test_registry_is_coherent(self):
        r = self.registry
        self.assertEqual(r["name_max_chars"], 128)
        self.assertEqual(r["max_custom_fields"], 256)
        self.assertFalse(set(r["namespaces"]) & set(r["reserved_namespaces"]))
        self.assertFalse(set(r["fields"]) & self.protected)
        for name, field in r["fields"].items():
            with self.subTest(field=name):
                self.assertIn(field["type"], r["value_types"])
                self.assertIsNone(registry_reason(r, self.protected, [name]))

    def test_cases_follow_the_reference_check(self):
        self.assertEqual(self.spec["check_order"], ["protected", "format", "registered_field", "reserved", "namespace"])
        for case in self.spec["config_cases"]:
            with self.subTest(case=case["id"]):
                reason = registry_reason(self.registry, self.protected, expand_names(case["names"]))
                self.assertEqual(reason is None, case["accepted"])
                self.assertEqual(reason, case.get("reason"))
        reasons = {c.get("reason") for c in self.spec["config_cases"]} - {None}
        self.assertEqual(reasons, {"protected", "format", "reserved", "namespace", "too_many"})

    def test_shared_allowed_fields_are_registered(self):
        suite = json.loads(SCENARIOS.read_text())
        for names in (suite["degradation_allowed_fields"], self.spec["value_allowed_fields"]):
            self.assertIsNone(registry_reason(self.registry, self.protected, names))
        for case in self.spec["value_cases"]:
            self.assertLessEqual(set(case["fields"]), set(self.spec["value_allowed_fields"]))

    def test_every_language_tests_every_field_registry_case(self):
        for case in self.spec["config_cases"] + self.spec["value_cases"]:
            for language in case["languages"]:
                text = (ROOT / FIELD_REGISTRY_TESTS[language]).read_text()
                with self.subTest(case=case["id"], language=language):
                    self.assertIn(case["id"], text)

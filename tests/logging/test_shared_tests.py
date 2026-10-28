import copy
import json
from pathlib import Path
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
            "go/observability/schema.json",
            "dotnet/packages/observability/src/schema.json",
        ]
        definitions = [json.loads((ROOT / p).read_text()) for p in paths]
        for definition in definitions[1:]:
            self.assertEqual(definitions[0], definition)
        self.assertIn("environment", definitions[0]["$defs"]["common"]["required"])
        self.assertTrue(self.suite["emission_cases"])

    def test_no_standalone_contract_distribution_remains(self):
        for path in [
            "contracts/log-correlation",
            "ts/packages/log-contract",
            "dotnet/src/OneNexus.LogContract",
            ".github/workflows/log-contract-release.yml",
        ]:
            self.assertFalse((ROOT / path).exists(), path)

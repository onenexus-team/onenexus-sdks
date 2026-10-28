#!/usr/bin/env python3
"""Compare observations from real language APIs with shared JSON scenarios."""

import json
from pathlib import Path
import re
import sys

SCENARIOS = Path(__file__).with_name("scenarios.json")


class BehaviorMismatch(ValueError):
    """A language implementation disagreed with the shared behavior."""


def require(condition, message):
    if not condition:
        raise BehaviorMismatch(message)


def check_results(results_path, scenarios_path=SCENARIOS):
    scenarios = json.loads(Path(scenarios_path).read_text())
    result = json.loads(Path(results_path).read_text())
    cases = {
        (kind, c["id"]): c
        for kind in ("record", "context")
        for c in scenarios[kind + "_cases"]
    }
    require(
        len(cases) == sum(len(scenarios[k + "_cases"]) for k in ("record", "context")),
        "duplicate_scenario",
    )
    require(
        isinstance(result["results"], list) and len(result["results"]) == len(cases),
        "incomplete_case_coverage",
    )
    seen, fresh = set(), set()
    for item in result["results"]:
        key = (item["kind"], item["id"])
        require(key in cases and key not in seen, "unexpected_or_duplicate_case")
        seen.add(key)
        case = cases[key]
        if item["kind"] == "record":
            require(item["errors"] == case["errors"], "record_result_mismatch")
            continue
        trace_id = item["trace_id"]
        require(
            isinstance(trace_id, str)
            and re.fullmatch(r"[0-9a-f]{32}", trace_id)
            and trace_id != "0" * 32,
            "invalid_trace_id",
        )
        incoming = case["traceparent"].split("-")
        parent = incoming[1] if len(incoming) >= 4 else None
        if case["preserve_trace"]:
            require(trace_id == parent, "trusted_context_not_preserved")
        else:
            require(
                trace_id != parent and trace_id not in fresh,
                "fresh_context_not_isolated",
            )
            fresh.add(trace_id)
        outgoing = item["outgoing_traceparent"]
        require(
            isinstance(outgoing, str)
            and re.fullmatch(r"00-" + trace_id + r"-[0-9a-f]{16}-00", outgoing)
            and outgoing.split("-")[2] != "0" * 16,
            "invalid_outgoing_context",
        )
        require(item["after_trace_id"] is None, "context_not_cleared")
    return len(cases)


if __name__ == "__main__":
    print(f"PASS: {check_results(Path(sys.argv[1]))} shared logging scenarios")

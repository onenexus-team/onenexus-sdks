from __future__ import annotations

import asyncio
import concurrent.futures
import importlib.util
import io
import json
import logging
import os
import re
import threading
from pathlib import Path

import pytest

from onenexus_observability import (
    CONTRACT_DIGEST,
    CONTRACT_VERSION,
    ContractViolation,
    LogConfig,
    bound_context,
    build_record,
    current_trace_id,
    incoming_context,
    install_handler,
    outgoing_headers,
    validate_record,
)

SCENARIOS = Path(os.environ.get("ONENEXUS_LOGGING_SCENARIOS", Path(__file__).resolve().parents[4] / "tests/logging/scenarios.json"))

CONFIG = LogConfig("test-api", "development", "region-1", frozenset({"operation_id", "attempt"}))


def logger_for(stream):
    logger = logging.Logger("package-test", logging.DEBUG)
    handler = install_handler(logger, CONFIG, stream=stream)
    return logger, handler


def adapter_results():
    vectors = json.loads(SCENARIOS.read_bytes())
    observations = []
    for case in vectors["record_cases"]:
        observations.append(
            {
                "kind": "record",
                "id": case["id"],
                "errors": validate_record(case["record"], case["profile"]),
            }
        )
    for case in vectors["context_cases"]:
        with bound_context(
            incoming_context(
                {"traceparent": case["traceparent"]},
                trusted=case["trusted"],
                preserve_sampling=False,
            )
        ):
            item = {
                "kind": "context",
                "id": case["id"],
                "trace_id": current_trace_id(),
                "outgoing_traceparent": outgoing_headers()["traceparent"],
            }
        item["after_trace_id"] = current_trace_id()
        observations.append(item)
    return {
        "adapter_protocol": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_sha256": CONTRACT_DIGEST,
        "results": observations,
    }


def test_all_shared_cases_through_real_package(tmp_path):
    spec = importlib.util.spec_from_file_location("logging_checker", SCENARIOS.parent / "check_results.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    output = tmp_path / "observed.json"
    result = adapter_results()
    output.write_text(json.dumps(result))
    assert checker.check_results(output, SCENARIOS) == len(result["results"])
    # Negative control: accepting one invalid input must fail the shared checker.
    invalid = next(x for x in result["results"] if x.get("errors"))
    invalid["errors"] = []
    output.write_text(json.dumps(result))
    with pytest.raises(checker.BehaviorMismatch, match="record_result_mismatch"):
        checker.check_results(output, SCENARIOS)


def test_actual_logger_fields_and_custom_fields():
    output = io.StringIO()
    logger, handler = logger_for(output)
    with bound_context(incoming_context({}, trusted=False)):
        expected = current_trace_id()
        logger.warning(
            "Request %s",
            "completed",
            extra={
                "event": "request.completed",
                "outcome": "success",
                "fields": {"operation_id": "op-1", "attempt": 1},
                "environment": "prod",
                "trace_id": "0" * 32,
            },
        )
    value = json.loads(output.getvalue())
    assert validate_record(value, "lifecycle") == []
    assert value["environment"] == "development"
    assert value["trace_id"] == expected
    assert value["level"] == "WARN"
    assert value["message"] == "Request completed"
    assert value["operation_id"] == "op-1"
    assert handler.dropped_records == 0
    output.seek(0)
    output.truncate()
    logger.info("System ready")
    assert "trace_id" not in json.loads(output.getvalue())


@pytest.mark.parametrize(
    "fields", [{"environment": "prod"}, {"Authorization": "private"}, {"prompt": "private"}]
)
def test_unapproved_or_reserved_fields_are_removed_and_counted(fields, capsys):
    output = io.StringIO()
    logger, handler = logger_for(output)
    logger.info("Marker line", extra={"fields": fields})
    value = json.loads(output.getvalue())
    assert value["message"] == "Marker line"
    assert value["environment"] == "development"
    assert value["logging.dropped_field_count"] == 1
    assert "private" not in output.getvalue()
    assert handler.dropped_records == 0
    assert capsys.readouterr().err == ""


def test_invalid_configuration_is_startup_error():
    for env in ("dev", "", "unknown"):
        with pytest.raises(ContractViolation):
            LogConfig("test", env, "r1")
    with pytest.raises(ValueError):
        LogConfig("test", "prod", "r1", frozenset({"trace_id"}))


def test_message_limits_json_and_error_safety(capsys):
    output = io.StringIO()
    logger, handler = logger_for(output)
    logger.info("界" * 400)
    logger.info("safe", extra={"fields": {"operation_id": float("nan")}})
    logger.info("safe", extra={"fields": {"operation_id": "x" * 4096}})
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [r["message"][-1] for r in rows] == ["\u2026", "e", "e"]
    assert len(rows[0]["message"].encode()) <= 1024 and rows[0]["logging.truncated"] is True
    assert "operation_id" not in rows[1] and rows[1]["logging.dropped_field_count"] == 1
    assert len(rows[2]["operation_id"].encode()) <= 1024 and rows[2]["logging.truncated"] is True
    # A message that cannot be formatted has no text to keep: dropped and counted.
    logger.info("bad %s %s", "argument")
    assert handler.dropped_records == 1
    try:
        raise RuntimeError("private-exception-marker")
    except RuntimeError:
        logger.exception("Operation failed")
    assert "private-exception-marker" not in output.getvalue()
    assert json.loads(output.getvalue().splitlines()[-1])["error.type"] == "RuntimeError"
    assert capsys.readouterr().err == ""


def _expand(value):
    if isinstance(value, dict) and set(value) == {"repeat", "count"}:
        return value["repeat"] * value["count"]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


def _raise_nested(message, depth):
    if depth > 1:
        _raise_nested(message, depth - 1)
    raise ValueError(message)


_LEVELS = {"INFO": logging.INFO, "WARN": logging.WARNING, "ERROR": logging.ERROR}
_SUITE = json.loads(SCENARIOS.read_bytes())


@pytest.mark.parametrize("case", _SUITE["degradation_cases"], ids=lambda c: c["id"])
def test_shared_degradation_scenarios(case):
    """The line still arrives: shortened, stripped or with its error, never dropped."""
    output = io.StringIO()
    logger = logging.Logger("degradation", logging.DEBUG)
    config = LogConfig("shared-test", "development", "region-1", frozenset(_SUITE["degradation_allowed_fields"]))
    handler = install_handler(logger, config, stream=output)
    message = _expand(case["message"])
    extra = {"fields": _expand(case["fields"])}
    if "error" in case:
        try:
            _raise_nested(case["error"]["message"], case["error"]["nested_calls"])
        except ValueError:
            logger.log(_LEVELS[case["level"]], "%s", message, extra=extra, exc_info=True)
    else:
        logger.log(_LEVELS[case["level"]], "%s", message, extra=extra)
    assert handler.dropped_records == 0
    (line,) = output.getvalue().splitlines()
    row = json.loads(line)
    assert validate_record(row) == []
    expect = case["expect"]
    assert row.get("logging.truncated") is expect["truncated"]
    assert row.get("logging.dropped_field_count") == expect["dropped_field_count"]
    if "message" in expect:
        assert row["message"] == _expand(expect["message"])
    else:
        assert len(row["message"].encode()) <= expect["message_max_bytes"]
        assert row["message"].startswith(expect["message_prefix"])
        assert row["message"].endswith(expect["message_suffix"])
    for key, value in _expand(expect.get("fields", {})).items():
        assert row[key] == value
    assert all(key not in row for key in expect.get("absent", []))
    for key, bound in expect.get("field_bounds", {}).items():
        assert len(row[key].encode()) <= bound["max_bytes"]
        assert row[key].startswith(bound["prefix"]) and row[key].endswith(bound["suffix"])
    if "record_max_bytes" in expect:
        assert len(line.encode()) <= expect["record_max_bytes"]
    if expect.get("error_type"):
        assert row["error.type"] == _SUITE["degradation_error_type"]["python"]
        stack = row["exception.stacktrace"]
        assert len(stack.encode()) <= expect["stacktrace_max_bytes"]
        assert all(re.fullmatch(expect["stacktrace_line_pattern"], frame) for frame in stack.split("\n"))
        assert stack.split("\n")[0].startswith("at _raise_nested (test_observability.py:")
        assert not any(marker in line for marker in expect["stacktrace_excludes"])
    handler.close()


def test_failed_sink_does_not_change_application_result(capsys):
    class BrokenStream(io.StringIO):
        def write(self, value):
            raise OSError("private-sink-error")

    logger, handler = logger_for(BrokenStream())
    logger.info("Safe event")
    assert handler.dropped_records == 1
    assert capsys.readouterr().err == ""


def test_initializer_is_idempotent_under_concurrent_calls():
    output = io.StringIO()
    logger = logging.Logger("initialize")
    other = logging.NullHandler()
    logger.addHandler(other)
    barrier = threading.Barrier(2)

    def install():
        barrier.wait(timeout=5)
        return install_handler(logger, CONFIG, stream=output)

    with concurrent.futures.ThreadPoolExecutor(2) as executor:
        values = list(executor.map(lambda _: install(), range(2)))
    assert values[0] is values[1]
    assert logger.handlers == [other, values[0]]
    with pytest.raises(ValueError, match="logging_configuration_conflict"):
        install_handler(logger, LogConfig("other", "prod", "r2"), stream=output)


def test_nested_exception_and_reused_worker_reset():
    assert current_trace_id() is None
    with bound_context(incoming_context({}, trusted=False)):
        parent = current_trace_id()
        for _ in range(2):
            with pytest.raises(RuntimeError), bound_context(incoming_context({}, trusted=False)):
                assert current_trace_id() != parent
                raise RuntimeError("test")
            assert current_trace_id() == parent
    assert current_trace_id() is None
    assert outgoing_headers() == {}


@pytest.mark.asyncio
async def test_concurrent_requests_and_cancellation_cleanup():
    ready = asyncio.Event()
    release = asyncio.Event()
    output = io.StringIO()
    logger, handler = logger_for(output)

    async def cancelled():
        try:
            with bound_context(incoming_context({}, trusted=False)):
                logger.info("Waiting", extra={"fields": {"operation_id": "cancelled"}})
                ready.set()
                await release.wait()
        finally:
            assert current_trace_id() is None

    task = asyncio.create_task(cancelled())
    await asyncio.wait_for(ready.wait(), 2)
    with bound_context(incoming_context({}, trusted=False)):
        logger.info("Other request", extra={"fields": {"operation_id": "other"}})
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        logger.info("Other request done", extra={"fields": {"operation_id": "other"}})
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert records[0]["trace_id"] != records[1]["trace_id"] == records[2]["trace_id"]
    assert handler.dropped_records == 0
    assert current_trace_id() is None


def test_thread_isolation_and_durable_metadata_roundtrip():
    with bound_context(incoming_context({}, trusted=False)):
        original = current_trace_id()
        metadata = json.loads(json.dumps(outgoing_headers()))

    def worker():
        assert current_trace_id() is None
        for attempt in (1, 2):
            with bound_context(incoming_context(metadata, trusted=True)):
                record = build_record(CONFIG, "Work", fields={"attempt": attempt})
                assert record["trace_id"] == original
            assert current_trace_id() is None

    with concurrent.futures.ThreadPoolExecutor(2) as executor:
        list(executor.map(lambda _: worker(), range(2)))


def test_sampling_and_existing_recorded_child_are_preserved():
    # Existing workspace dependency; not a runtime requirement of this package.
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    incoming = "00-11111111111111111111111111111111-2222222222222222-01"
    with bound_context(
        incoming_context({"traceparent": incoming, "baggage": "secret=x"}, trusted=True)
    ):
        with tracer.start_as_current_span("child") as child:
            assert child.is_recording()
            assert current_trace_id() == "1" * 32
            assert outgoing_headers()["traceparent"].endswith("-01")
            assert (
                outgoing_headers()["traceparent"].split("-")[2]
                == f"{child.get_span_context().span_id:016x}"
            )
            assert set(outgoing_headers()) == {"traceparent"}
            assert build_record(CONFIG, "Inside child")["trace_id"] == "1" * 32
    assert current_trace_id() is None
    provider.shutdown()


def test_malformed_and_duplicate_header_boundaries():
    header = "00-11111111111111111111111111111111-2222222222222222-01"
    with bound_context(incoming_context({"TraceParent": header}, trusted=True)):
        assert current_trace_id() == "1" * 32
    with bound_context(
        incoming_context({"traceparent": header, "TraceParent": header}, trusted=True)
    ):
        assert current_trace_id() != "1" * 32


def test_integration_probe_negative_control(tmp_path):
    import subprocess
    import sys

    probe = Path(__file__).resolve().parent / "integration/log_probe.py"
    capture = tmp_path / "logs.ndjson"
    args = [
        sys.executable,
        str(probe),
        "--environment",
        "development",
        "--region",
        "test",
        "--run-id",
        "51386ccb-5346-4e7a-a040-bc32bf742cc1",
    ]
    emitted = subprocess.run(args, capture_output=True, text=True, timeout=10, check=True)
    capture.write_text(emitted.stdout)
    subprocess.run(args + ["--verify", str(capture)], capture_output=True, timeout=10, check=True)
    records = [json.loads(line) for line in emitted.stdout.splitlines()]
    del records[0]["trace_id"]
    capture.write_text("".join(json.dumps(record) + "\n" for record in records))
    result = subprocess.run(args + ["--verify", str(capture)], capture_output=True, timeout=10)
    assert result.returncode != 0


def test_single_distribution_has_no_contract_dependency():
    from importlib.metadata import requires
    assert not any("onenexus-log-contract" in item for item in requires("onenexus-observability-python") or [])


@pytest.mark.parametrize("case", json.loads(SCENARIOS.read_bytes())["emission_cases"], ids=lambda c: c["id"])
def test_shared_emission_scenarios(case):
    from opentelemetry.context import Context
    output = io.StringIO()
    logger = logging.Logger("shared", logging.DEBUG)
    handler = install_handler(logger, LogConfig("shared-test", "development", "region-1"), stream=output)
    ctx = incoming_context({"traceparent": case["traceparent"]}, trusted=True) if case["traceparent"] else Context()
    with bound_context(ctx):
        logger.info(case["message"])
    rows = output.getvalue().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    for key, value in case["expected"].items():
        assert row[key] == value
    assert all(key not in row for key in case.get("absent", []))
    assert validate_record(row) == []
    handler.close()


def _recurse(depth):
    if depth:
        _recurse(depth - 1)
    raise KeyError("private-key-marker")


def test_caller_error_fields_win_and_exception_text_never_logged():
    output = io.StringIO()
    logger = logging.Logger("caller-error", logging.DEBUG)
    config = LogConfig("test-api", "development", "region-1", frozenset({"error.type"}))
    install_handler(logger, config, stream=output)
    try:
        _recurse(0)
    except KeyError:
        logger.exception("Lookup failed", extra={"fields": {"error.type": "LookupFailed"}})
    row = json.loads(output.getvalue())
    assert row["error.type"] == "LookupFailed"
    assert row["exception.stacktrace"].startswith("at _recurse (test_observability.py:")
    assert "private-key-marker" not in output.getvalue()


def test_deep_stack_keeps_innermost_frames_within_budget():
    output = io.StringIO()
    logger, handler = logger_for(output)
    try:
        _recurse(200)
    except KeyError:
        logger.exception("Lookup failed")
    row = json.loads(output.getvalue())
    frames = row["exception.stacktrace"].split("\n")
    assert len(row["exception.stacktrace"].encode()) <= 2048
    assert row["logging.truncated"] is True
    assert frames[0].startswith("at _recurse (") and len(frames) < 200
    assert handler.dropped_records == 0


def test_stack_is_shortened_before_any_field_is_removed():
    output = io.StringIO()
    logger = logging.Logger("fit", logging.DEBUG)
    config = LogConfig("test-api", "development", "region-1", frozenset({"a", "b"}))
    install_handler(logger, config, stream=output)
    try:
        _recurse(200)
    except KeyError:
        logger.exception("m" * 900, extra={"fields": {"a": "x" * 900, "b": "y" * 900}})
    line = output.getvalue().strip()
    row = json.loads(line)
    assert len(line.encode()) <= 4096
    assert row["a"] == "x" * 900 and row["b"] == "y" * 900
    assert "logging.dropped_field_count" not in row
    assert row["logging.truncated"] is True and row["exception.stacktrace"].startswith("at _recurse")


def test_build_record_strips_unknown_fields_instead_of_raising():
    record = build_record(CONFIG, "Ready", fields={"operation_id": "op-1", "unknown": "x"})
    assert record["operation_id"] == "op-1" and "unknown" not in record
    assert record["logging.dropped_field_count"] == 1
    assert validate_record(record) == []


def test_dropped_field_count_is_capped_so_the_line_stays_valid():
    output = io.StringIO()
    logger, handler = logger_for(output)
    logger.info("Many fields", extra={"fields": {f"unknown{i}": i for i in range(100)}})
    row = json.loads(output.getvalue())
    assert row["logging.dropped_field_count"] == 64
    assert handler.dropped_records == 0


def test_malformed_unicode_field_is_removed_not_the_record():
    output = io.StringIO()
    logger, handler = logger_for(output)
    logger.info("Ready", extra={"fields": {"operation_id": "ok\udc80x", "attempt": 1}})
    row = json.loads(output.getvalue())
    assert "operation_id" not in row and row["attempt"] == 1
    assert row["logging.dropped_field_count"] == 1 and handler.dropped_records == 0


def test_a_caller_stack_that_wins_never_inherits_the_sdk_cut_flag():
    output = io.StringIO()
    logger = logging.Logger("caller-stack", logging.DEBUG)
    config = LogConfig("test-api", "development", "region-1", frozenset({"exception.stacktrace"}))
    install_handler(logger, config, stream=output)
    try:
        _recurse(200)
    except KeyError:
        logger.exception("Lookup failed", extra={"fields": {"exception.stacktrace": "at caller (app.py:1)"}})
    row = json.loads(output.getvalue())
    assert row["exception.stacktrace"] == "at caller (app.py:1)"
    assert "logging.truncated" not in row and row["error.type"] == "KeyError"


def test_request_fields_are_never_removed_to_fit_a_record():
    output = io.StringIO()
    logger = logging.Logger("fit-request", logging.DEBUG)
    names = [f"f{i}" for i in range(8)]
    config = LogConfig("test-api", "development", "region-1", frozenset(names))
    install_handler(logger, config, stream=output)
    route = "/items/" + "r" * 500  # the largest field, and a request field
    fields = {"http.route": route, **{name: "x" * 400 for name in names}}
    logger.info("m" * 1000, extra={"fields": fields})
    line = output.getvalue().strip()
    row = json.loads(line)
    assert len(line.encode()) <= 4096
    assert row["http.route"] == route
    assert row["logging.dropped_field_count"] >= 1

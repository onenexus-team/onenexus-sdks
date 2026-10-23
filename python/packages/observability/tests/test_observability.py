from __future__ import annotations

import asyncio
import concurrent.futures
import importlib.util
import io
import json
import logging
import threading
from importlib.resources import files
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

CONFIG = LogConfig("test-api", "development", "region-1", frozenset({"operation_id", "attempt"}))


def logger_for(stream):
    logger = logging.Logger("package-test", logging.DEBUG)
    handler = install_handler(logger, CONFIG, stream=stream)
    return logger, handler


def adapter_results():
    root = files("onenexus_observability").joinpath("_contract")
    vectors = json.loads(root.joinpath("vectors.json").read_bytes())
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
    root = Path(str(files("onenexus_observability").joinpath("_contract")))
    spec = importlib.util.spec_from_file_location("release_checker", root / "check_contract.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    output = tmp_path / "observed.json"
    result = adapter_results()
    output.write_text(json.dumps(result))
    assert checker.check_results(CONTRACT_VERSION, CONTRACT_DIGEST, output, root) == 66
    # Negative control: accepting one invalid input must fail the shared checker.
    invalid = next(x for x in result["results"] if x.get("errors"))
    invalid["errors"] = []
    output.write_text(json.dumps(result))
    with pytest.raises(checker.ContractError, match="record_result_mismatch"):
        checker.check_results(CONTRACT_VERSION, CONTRACT_DIGEST, output, root)


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
def test_unapproved_or_reserved_fields_fail_without_echo(fields, capsys):
    output = io.StringIO()
    logger, handler = logger_for(output)
    logger.info("private marker", extra={"fields": fields})
    assert handler.dropped_records == 1
    assert output.getvalue() == ""
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
    logger.info("bad %s %s", "argument")
    assert handler.dropped_records == 4
    assert output.getvalue() == ""
    try:
        raise RuntimeError("private-exception-marker")
    except RuntimeError:
        logger.exception("Operation failed")
    assert "private-exception-marker" not in output.getvalue()
    assert capsys.readouterr().err == ""


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


def test_raw_probe_negative_control(tmp_path):
    import subprocess
    import sys

    probe = Path(__file__).resolve().parents[1] / "raw_tests/log_probe.py"
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


def test_tampered_installed_bundle_fails_before_logging(tmp_path):
    import os
    import shutil
    import subprocess
    import sys

    package = Path(str(files("onenexus_observability")))
    copied = tmp_path / "onenexus_observability"
    shutil.copytree(package, copied, ignore=shutil.ignore_patterns("__pycache__"))
    schema = copied / "_contract/schema.json"
    schema.write_bytes(schema.read_bytes() + b" ")
    result = subprocess.run(
        [sys.executable, "-c", "import onenexus_observability"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "contract_integrity_failed" in result.stderr

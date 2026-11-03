import asyncio
import io
import json
import logging
import os
from pathlib import Path

import pytest
from opentelemetry.context import Context

from onenexus_observability import (
    ContractViolation,
    LogConfig,
    build_record,
    bound_context,
    incoming_context,
    current_request_fields,
    install_handler,
    request_log_context,
    validate_record,
)

CONFIG = LogConfig("request-test", "development", "test")
TENANT = "1" * 32
OWNER = f"nx1://test/{TENANT}/CAS/global/User/" + "2" * 32
SCENARIOS = Path(
    os.environ.get(
        "ONENEXUS_LOGGING_SCENARIOS",
        Path(__file__).resolve().parents[4] / "tests/logging/scenarios.json",
    )
)


def test_shared_request_emissions_and_ambient_application_logs():
    for case in json.loads(SCENARIOS.read_text())["request_emission_cases"]:
        output = io.StringIO()
        logger = logging.Logger("request-test", logging.INFO)
        handler = install_handler(logger, CONFIG, stream=output)
        correlation = (
            incoming_context({"traceparent": case["traceparent"]}, trusted=True)
            if case["traceparent"]
            else Context()
        )
        with bound_context(correlation), request_log_context() as receipt:
            receipt.bind_verified_identity(case["principal"], case["tenant"])
            if case["error"]:
                receipt.set_error(case["error"])
            logger.info("Application event", extra={"fields": {"principal_id": "spoofed"}})
            logger.info(
                "Request finished",
                extra={
                    "fields": receipt.terminal_fields(
                        "POST",
                        "/items/{id}",
                        case["status"],
                        1.5,
                        interrupted=case["interrupted"],
                    )
                },
            )
        logger.info("Outside request")
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        assert handler.dropped_records == 0
        assert rows[0]["principal_id"] == case["principal"]
        assert all(rows[1][k] == v for k, v in case["expected"].items())
        assert validate_record(rows[1], "request") == []
        assert "principal_id" not in rows[2]
        assert all("request_id" not in row for row in rows)
        if case["traceparent"] is None:
            assert "trace_id" not in rows[1]  # Never fabricate a trace at a service boundary.


def test_request_profile_cannot_be_bypassed_at_emission():
    with pytest.raises(ContractViolation):
        build_record(CONFIG, "Missing fields", fields={"request_event": "completed"})
    with request_log_context() as receipt:
        for status, duration in [(None, 1), (600, 1), (200, -1), (200, float("nan"))]:
            with pytest.raises(ContractViolation):
                build_record(
                    CONFIG,
                    "Invalid request",
                    fields=receipt.terminal_fields("GET", "/items", status, duration),
                )


def test_attribution_validation_nested_scope_and_cleanup():
    with request_log_context() as receipt:
        receipt.bind_verified_identity(OWNER, TENANT)
        with request_log_context():
            assert current_request_fields()["principal_id"] is None
        assert current_request_fields()["principal_id"] == OWNER
        for principal, tenant in [(OWNER, "3" * 32), ("username", TENANT), (OWNER, "0" * 32)]:
            receipt.bind_verified_identity(principal, tenant)
            assert receipt.fields()["principal_id"] is None
        with pytest.raises(ValueError, match="invalid_error_code"):
            receipt.set_error("secret message")
    receipt.bind_verified_identity(OWNER, TENANT)
    receipt.set_error("LATE")
    assert receipt.fields() == current_request_fields() == {}
    with pytest.raises(ValueError, match="request_context_closed"):
        receipt.terminal_fields("GET", "/", 200, 1)
    with pytest.raises(RuntimeError):
        with request_log_context():
            raise RuntimeError()
    assert current_request_fields() == {}


@pytest.mark.asyncio
async def test_concurrent_requests_and_detached_child_cannot_retain_identity():
    async def run(index):
        with request_log_context() as receipt:
            principal = OWNER.rsplit("/", 1)[0] + f"/{index + 1:032x}"
            receipt.bind_verified_identity(principal, TENANT)
            await asyncio.sleep(0)
            assert current_request_fields()["principal_id"] == principal

    await asyncio.gather(*(run(i) for i in range(20)))
    resume = asyncio.Event()
    with request_log_context() as receipt:
        receipt.bind_verified_identity(OWNER, TENANT)

        async def child():
            await resume.wait()
            receipt.bind_verified_identity(OWNER, TENANT)
            return current_request_fields()

        task = asyncio.create_task(child())
    resume.set()
    assert await task == {}
    entered = asyncio.Event()

    async def cancelled():
        with request_log_context() as receipt:
            receipt.bind_verified_identity(OWNER, TENANT)
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(cancelled())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert current_request_fields() == {}

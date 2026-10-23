"""Emit/verify synthetic logs from the installed wheel; no credentials or business calls."""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

from onenexus_observability import (
    LogConfig,
    bound_context,
    current_trace_id,
    incoming_context,
    install_handler,
    outgoing_headers,
    validate_record,
)


def emit(environment, region, run_id):
    logger = logging.Logger("raw-log-probe", logging.INFO)
    handler = install_handler(
        logger,
        LogConfig(
            "observability-package-probe",
            environment,
            region,
            frozenset({"operation_id", "attempt"}),
        ),
    )
    with bound_context(incoming_context({}, trusted=False)):
        trace_id = current_trace_id()
        metadata = json.loads(json.dumps(outgoing_headers()))
        logger.info(
            "Probe accepted",
            extra={
                "event": "probe.accepted",
                "outcome": "success",
                "fields": {"operation_id": run_id},
            },
        )
    # Restore durable metadata after the original context has ended.
    for attempt in (1, 2):
        with bound_context(incoming_context(metadata, trusted=True)):
            logger.info(
                "Probe attempt completed",
                extra={
                    "event": "probe.attempt",
                    "outcome": "success",
                    "fields": {"operation_id": run_id, "attempt": attempt},
                },
            )
    logger.info("Probe context cleared", extra={"fields": {"operation_id": run_id}})
    if handler.dropped_records or current_trace_id() is not None:
        raise RuntimeError("probe_failed")
    print(json.dumps({"run_id": run_id, "trace_id": trace_id}), file=sys.stderr)


def verify(path, environment, region, run_id):
    records = []
    with path.open("rb") as stream:
        for _ in range(5):
            line = stream.readline(4098)
            if not line:
                break
            if len(line) > 4097:
                raise ValueError("record_too_large")
            records.append(json.loads(line))
    if len(records) != 4:
        raise ValueError("unexpected_record_count")
    for record in records:
        if validate_record(record, "lifecycle" if "event" in record else "common"):
            raise ValueError("invalid_record")
        if record.get("service") != "observability-package-probe":
            raise ValueError("service_mismatch")
        if (record["environment"], record["region"], record.get("operation_id")) != (
            environment,
            region,
            run_id,
        ):
            raise ValueError("scope_mismatch")
    if len({r["trace_id"] for r in records[:3]}) != 1 or "trace_id" in records[-1]:
        raise ValueError("context_mismatch")
    if [r.get("event") for r in records] != [
        "probe.accepted",
        "probe.attempt",
        "probe.attempt",
        None,
    ]:
        raise ValueError("event_mismatch")
    if [r["attempt"] for r in records[1:3]] != [1, 2]:
        raise ValueError("attempt_mismatch")
    print("PASS: four scoped records; retry correlation and context cleanup")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True, choices=["development", "staging", "prod"])
    parser.add_argument("--region", required=True)
    parser.add_argument("--run-id", required=True, type=str)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    uuid.UUID(args.run_id)
    if args.verify:
        verify(args.verify, args.environment, args.region, args.run_id)
    else:
        emit(args.environment, args.region, args.run_id)


if __name__ == "__main__":
    main()

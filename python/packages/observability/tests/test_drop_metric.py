"""One drop metric (tests/logging/scenarios.json `drop_metric`, design review R1).

Each test uses its own service name: the counter is process-wide.
"""

from __future__ import annotations

import io
import json
import logging
import os
import threading
from pathlib import Path

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from onenexus_observability import (
    DropCount,
    DropReason,
    JsonLogHandler,
    LogConfig,
    LogDropCounter,
    drop_metrics_text,
    log_drop_counts,
    register_drop_metric,
)
from onenexus_observability import drop_metric as sdk_drop_metric

ROOT = Path(__file__).resolve().parents[4]
METRIC = json.loads((ROOT / "tests/logging/scenarios.json").read_text())["drop_metric"]


class Gate(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.open = threading.Event()

    def write(self, value: str) -> int:
        self.open.wait()
        return super().write(value)


class FailFirst(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    def write(self, value: str) -> int:
        if not self.failed:
            self.failed = True
            raise OSError("broken pipe")
        return super().write(value)


def handler_for(
    service: str, stream: io.StringIO | None = None, **kwargs
) -> tuple[logging.Logger, JsonLogHandler]:
    handler = JsonLogHandler(
        LogConfig(service, "development", "region-1"), stream or io.StringIO(), **kwargs
    )
    logger = logging.Logger(f"drop-{service}-{id(handler)}", logging.INFO)
    logger.addHandler(handler)
    return logger, handler


def rows(service: str) -> dict[str, int]:
    return {row.reason: row.count for row in log_drop_counts() if row.service == service}


def zero_rows() -> dict[str, int]:
    return dict.fromkeys(METRIC["reasons"], 0)


def test_the_constants_match_the_shared_spec():
    assert sdk_drop_metric.OTEL_NAME == METRIC["otel_name"]
    assert sdk_drop_metric.OTEL_UNIT == METRIC["otel_unit"]
    assert sdk_drop_metric.PROMETHEUS_NAME == METRIC["prometheus_name"]
    assert sdk_drop_metric.HELP == METRIC["help"]
    assert [reason.value for reason in DropReason] == METRIC["reasons"]


def test_every_reason_reported_from_first_handler():
    _, handler = handler_for("drop-first")
    assert [row for row in log_drop_counts() if row.service == "drop-first"] == [
        DropCount("drop-first", DropReason(reason), 0) for reason in METRIC["reasons"]
    ]
    handler.close()


def test_each_reason_counted():
    service = "drop-each"
    # invalid: fields that are not a mapping are rejected.
    logger, handler = handler_for(service)
    logger.info("x", extra={"fields": object()})
    # io_errors: the first write fails.
    failing_logger, failing = handler_for(service, FailFirst())
    failing_logger.info("fails")
    failing_logger.info("written")
    assert failing.close_within() is True
    # queue_full: a blocked output with a queue of one.
    gate = Gate()
    blocked_logger, blocked = handler_for(service, gate, queue_capacity=1)
    for i in range(5):
        blocked_logger.info("line %s", i)
    blocked_queue_full = blocked.stats()["queue_full"]
    gate.open.set()
    assert blocked.close_within() is True
    # closed: a line after close.
    handler.close()
    logger.info("too late")

    assert rows(service) == {
        "closed": 1,
        "invalid": 1,
        "io_errors": 1,
        "queue_full": blocked_queue_full,
    }
    assert blocked_queue_full >= 3  # one in the write, one queued, the rest dropped
    for reason in METRIC["reasons"]:
        assert rows(service)[reason] == sum(h.stats()[reason] for h in (handler, failing, blocked))


def test_handlers_of_one_service_are_summed():
    service = "drop-summed"
    first_logger, first = handler_for(service)
    second_logger, second = handler_for(service)
    first.close()
    second.close()
    first_logger.info("a")
    second_logger.info("b")
    second_logger.info("c")
    assert (first.stats()["closed"], second.stats()["closed"]) == (1, 2)
    assert rows(service) == {**zero_rows(), "closed": 3}
    assert sum(1 for row in log_drop_counts() if row.service == service) == len(METRIC["reasons"])


def test_services_are_separate():
    a_logger, a = handler_for("drop-sep-a")
    _, b = handler_for("drop-sep-b")
    a.close()
    a_logger.info("dropped in a only")
    assert rows("drop-sep-a") == {**zero_rows(), "closed": 1}
    assert rows("drop-sep-b") == zero_rows()
    b.close()


def test_counts_survive_close():
    service = "drop-survive"
    logger, handler = handler_for(service)
    logger.info("x", extra={"fields": object()})
    assert rows(service)["invalid"] == 1
    assert handler.close_within() is True
    assert rows(service) == {**zero_rows(), "invalid": 1}
    del handler, logger  # a collected handler keeps its rows too
    assert rows(service) == {**zero_rows(), "invalid": 1}


def test_prometheus_text_format():
    example = METRIC["prometheus_text_example"]
    counts = [
        DropCount(c["service"], DropReason(c["reason"]), c["count"]) for c in example["counts"]
    ]
    assert drop_metrics_text(counts) == example["text"]


def test_prometheus_text_defaults_to_the_live_snapshot():
    logger, handler = handler_for("drop-live-text")
    handler.close()
    logger.info("late")
    text = drop_metrics_text()
    assert text.startswith(f"# HELP {METRIC['prometheus_name']} {METRIC['help']}\n")
    assert f'{METRIC["prometheus_name"]}{{service="drop-live-text",reason="closed"}} 1\n' in text
    assert f'{METRIC["prometheus_name"]}{{service="drop-live-text",reason="invalid"}} 0\n' in text


def test_otel_asynchronous_counter():
    service = "drop-otel"
    logger, handler = handler_for(service)
    handler.close()
    logger.info("late")
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    instrument = register_drop_metric(provider.get_meter("drop-metric-test"))
    assert instrument.name == METRIC["otel_name"]
    data = reader.get_metrics_data()
    metrics = [m for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics]
    assert [m.name for m in metrics] == [METRIC["otel_name"]]
    metric = metrics[0]
    assert metric.unit == METRIC["otel_unit"]
    assert metric.description == METRIC["help"]
    assert metric.data.is_monotonic is True
    points = {
        (p.attributes["service"], p.attributes["reason"]): p.value for p in metric.data.data_points
    }
    assert len(points) == len(log_drop_counts())
    assert {reason: points[(service, reason)] for reason in METRIC["reasons"]} == {
        **zero_rows(),
        "closed": 1,
    }
    provider.shutdown()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs os.fork")
def test_a_forked_child_starts_its_counts_at_zero():
    service = "drop-fork"
    logger, handler = handler_for(service)
    logger.info("x", extra={"fields": object()})
    pid = os.fork()
    if pid == 0:  # child: a new process, its own counts; the rows are kept
        ok = False
        try:
            before = rows(service) == zero_rows() and handler.stats()["invalid"] == 0
            logger.info("y", extra={"fields": object()})
            ok = before and rows(service) == {**zero_rows(), "invalid": 1}
        finally:
            os._exit(0 if ok else 3)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0
    assert rows(service) == {**zero_rows(), "invalid": 1}  # the parent's count is unchanged
    handler.close()


def test_an_adapter_counter_reports_and_counts_like_a_handler():
    service = "adapter-counter"
    counter = LogDropCounter(service)
    assert rows(service) == zero_rows()
    counter.add(DropReason.INVALID)
    counter.add("io_errors")
    LogDropCounter(service).add(DropReason.INVALID)
    assert rows(service) == {"closed": 0, "invalid": 2, "io_errors": 1, "queue_full": 0}
    with pytest.raises(ValueError):
        counter.add("too_large")

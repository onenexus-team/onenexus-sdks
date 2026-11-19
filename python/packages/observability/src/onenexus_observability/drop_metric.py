"""One drop metric (design review R1; tests/logging/scenarios.json ``drop_metric``).

Every line a handler does not write is counted once, process-wide, per
``(service, reason)``. The counts are read as a snapshot, as Prometheus text, or
through an OpenTelemetry asynchronous counter.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum

from opentelemetry.metrics import CallbackOptions, Meter, ObservableCounter, Observation

OTEL_NAME = "onenexus.log.records.dropped"
OTEL_UNIT = "{record}"
PROMETHEUS_NAME = "onenexus_log_records_dropped_total"
HELP = "Log records the logging SDK did not write, by reason."


class DropReason(StrEnum):
    """The write-model counters that mean "not written"."""

    CLOSED = "closed"
    INVALID = "invalid"
    IO_ERRORS = "io_errors"
    QUEUE_FULL = "queue_full"


@dataclass(frozen=True, order=True)
class DropCount:
    """One row; ordered by service, then reason."""

    service: str
    reason: DropReason
    count: int


class _DropCounter:
    """One lock guards the counts; it is never held across I/O."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, DropReason], int] = {}

    def register(self, service: str) -> None:
        """Report every reason for ``service`` at 0 from its first handler on."""
        with self._lock:
            for reason in DropReason:
                self._counts.setdefault((service, reason), 0)

    def add(self, service: str, reason: DropReason) -> None:
        with self._lock:
            self._counts[(service, reason)] = self._counts.get((service, reason), 0) + 1

    def snapshot(self) -> list[DropCount]:
        with self._lock:
            items = list(self._counts.items())
        return sorted(DropCount(service, reason, count) for (service, reason), count in items)

    def after_fork_in_child(self) -> None:
        """A forked child is a new process: its counts start at 0 (rows are kept).

        The lock is replaced: the parent's may be held by a thread the child lacks.
        """
        self._lock = threading.Lock()
        self._counts = dict.fromkeys(self._counts, 0)


_DROPS = _DropCounter()


def log_drop_counts() -> list[DropCount]:
    """Every ``(service, reason)`` row, sorted by service then reason."""
    return _DROPS.snapshot()


class LogDropCounter:
    """Counts drops for an adapter that builds records with the SDK but owns its sink.

    Creating it reports every reason for ``service`` at 0, like a handler does.
    """

    def __init__(self, service: str) -> None:
        self._service = service
        _DROPS.register(service)

    def add(self, reason: DropReason) -> None:
        """Count one record not written, for ``reason``."""
        _DROPS.add(self._service, DropReason(reason))


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def drop_metrics_text(counts: Iterable[DropCount] | None = None) -> str:
    """Prometheus text exposition of ``counts`` (default: the live snapshot)."""
    rows = sorted(counts) if counts is not None else log_drop_counts()
    lines = [f"# HELP {PROMETHEUS_NAME} {HELP}", f"# TYPE {PROMETHEUS_NAME} counter"]
    lines += [
        f'{PROMETHEUS_NAME}{{service="{_label(row.service)}",reason="{_label(row.reason)}"}} '
        f"{row.count}"
        for row in rows
    ]
    return "\n".join(lines) + "\n"


def _observe(_options: CallbackOptions) -> Iterator[Observation]:
    for row in log_drop_counts():
        yield Observation(row.count, {"service": row.service, "reason": str(row.reason)})


def register_drop_metric(meter: Meter) -> ObservableCounter:
    """Create the asynchronous monotonic counter ``OTEL_NAME`` on ``meter``."""
    return meter.create_observable_counter(
        name=OTEL_NAME, callbacks=[_observe], unit=OTEL_UNIT, description=HELP
    )

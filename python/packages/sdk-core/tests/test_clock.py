from __future__ import annotations

from datetime import UTC, datetime, timedelta

from onenexus_sdk_core import Clock, SystemClock


def test_system_clock_satisfies_protocol() -> None:
    assert isinstance(SystemClock(), Clock)


def test_system_clock_tracks_observed_server_delta() -> None:
    clock = SystemClock()
    future = datetime.now(UTC) + timedelta(seconds=120)
    clock.observe_server_time(future)
    assert clock.server_now() > datetime.now(UTC) + timedelta(seconds=110)


def test_system_clock_normalizes_naive_datetime() -> None:
    clock = SystemClock()
    naive = (datetime.now(UTC) + timedelta(seconds=60)).replace(tzinfo=None)
    clock.observe_server_time(naive)
    assert clock.server_now() > datetime.now(UTC) + timedelta(seconds=50)

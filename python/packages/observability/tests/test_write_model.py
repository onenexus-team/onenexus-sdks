"""The shared write model (tests/logging/scenarios.json `write_model`, design review F2).

The caller never waits on the output; a bounded queue feeds one background
writer; a full queue drops and counts; a write error is counted and the writer
continues; close drains until a deadline. Python also restarts the writer after
os.fork and never turns a blocked stdout at exit into a crash.
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from onenexus_observability import JsonLogHandler, LogConfig
from onenexus_observability import logging as sdk_logging

ROOT = Path(__file__).resolve().parents[4]
MODEL = json.loads((ROOT / "tests/logging/scenarios.json").read_text())["write_model"]
CONFIG = LogConfig("write-model", "development", "region-1")


class Gate(io.StringIO):
    """A stream whose writes wait until released (a blocked pipe, without a pipe)."""

    def __init__(self) -> None:
        super().__init__()
        self.open = threading.Event()

    def write(self, value: str) -> int:
        self.open.wait()
        return super().write(value)


class FailFirst(io.StringIO):
    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self.error = error

    def write(self, value: str) -> int:
        if self.error is not None:
            error, self.error = self.error, None
            raise error
        return super().write(value)


class Slow(io.StringIO):
    def write(self, value: str) -> int:
        time.sleep(0.01)
        return super().write(value)


def logger_for(stream, **kwargs) -> tuple[logging.Logger, JsonLogHandler]:
    logger = logging.Logger(f"write-model-{id(stream)}", logging.INFO)
    handler = JsonLogHandler(CONFIG, stream, **kwargs)
    logger.addHandler(handler)
    return logger, handler


def lines(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in io.StringIO.getvalue(stream).splitlines()]


def test_the_constants_match_the_shared_model():
    assert sdk_logging.QUEUE_CAPACITY == MODEL["queue_capacity"]
    assert sdk_logging.ERROR_WAIT_SECONDS * 1000 == MODEL["error_wait_ms"]
    assert sdk_logging.CLOSE_TIMEOUT_SECONDS * 1000 == MODEL["close_timeout_ms"]
    _, handler = logger_for(io.StringIO())
    assert set(handler.stats()) == set(MODEL["counters"])
    handler.close()


def test_blocked_output_never_blocks_caller():
    stream = Gate()
    logger, handler = logger_for(stream)
    total = 3000
    slowest = 0.0
    for i in range(total):
        start = time.perf_counter()
        logger.info("line %s", i)
        slowest = max(slowest, time.perf_counter() - start)
    stats = handler.stats()
    assert slowest * 1000 < MODEL["caller_budget_ms"], slowest
    assert stats["queue_full"] >= total - MODEL["queue_capacity"] - 1
    stream.open.set()  # the output recovers: queued lines are written
    assert handler.close_within() is True
    stats = handler.stats()
    assert stats["written"] == total - stats["queue_full"]
    assert handler.dropped_records == stats["queue_full"]


def test_write_error_recovers():
    stream = FailFirst(OSError("broken pipe"))
    logger, handler = logger_for(stream)
    for i in range(3):
        logger.info("line %s", i)
    assert handler.close_within() is True
    assert (handler.stats()["io_errors"], handler.stats()["written"]) == (1, 2)
    assert [r["message"] for r in lines(stream)] == ["line 1", "line 2"]


def test_partial_write_recovers():
    # A text stream reports a partial write through BlockingIOError.
    partial = BlockingIOError(11, "would block", 7)
    stream = FailFirst(partial)
    logger, handler = logger_for(stream)
    logger.info("line 0")
    logger.info("line 1")
    assert handler.close_within() is True
    text = io.StringIO.getvalue(stream)
    assert text.startswith("\n")  # the cut line is ended before the next one
    assert [json.loads(line)["message"] for line in text.splitlines() if line] == ["line 1"]


def test_partial_write_recovers_on_a_file_descriptor(monkeypatch):
    read_end, write_end = os.pipe()
    real_write = os.write
    calls = {"n": 0}

    def flaky(fd, data):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_write(fd, data[:5])  # part of line 0 ...
        if calls["n"] == 2:
            raise OSError("broken pipe")  # ... and the rest fails
        return real_write(fd, data)

    monkeypatch.setattr(sdk_logging.os, "write", flaky)
    stream = os.fdopen(write_end, "w")
    logger, handler = logger_for(stream)
    logger.info("line 0")
    logger.info("line 1")
    assert handler.close_within() is True
    stream.close()
    with os.fdopen(read_end) as reader:
        text = reader.read()
    first, second = text.split("\n")[:2]
    assert len(first) == 5  # the cut line, ended by a newline
    assert json.loads(second)["message"] == "line 1"
    assert (handler.stats()["io_errors"], handler.stats()["written"]) == (1, 1)


def test_a_short_os_write_is_completed_not_counted_as_an_error(monkeypatch):
    read_end, write_end = os.pipe()
    real_write = os.write
    monkeypatch.setattr(sdk_logging.os, "write", lambda fd, data: real_write(fd, data[:3]))
    stream = os.fdopen(write_end, "w")
    logger, handler = logger_for(stream)
    logger.info("line 0")
    assert handler.close_within() is True
    stream.close()
    with os.fdopen(read_end) as reader:
        assert json.loads(reader.read())["message"] == "line 0"
    assert handler.stats()["io_errors"] == 0


def test_close_drains():
    stream = Slow()
    logger, handler = logger_for(stream)
    for i in range(10):
        logger.info("line %s", i)
    assert handler.close_within() is True
    assert handler.stats()["written"] == 10 and handler.stats()["pending"] == 0


def test_close_deadline():
    stream = Gate()
    logger, handler = logger_for(stream)
    for i in range(5):
        logger.info("line %s", i)
    start = time.monotonic()
    assert handler.close_within(0.3) is False
    assert time.monotonic() - start < 0.3 + 0.5
    # Undelivered lines stay counted: 4 queued + 1 stuck in the blocked write
    # (the internal stop marker is not a line).
    assert handler.stats()["pending"] == 5
    stream.open.set()


def test_log_after_close():
    stream = io.StringIO()
    logger, handler = logger_for(stream)
    handler.close()
    logger.info("too late")
    assert handler.stats()["closed"] == 1 and handler.stats()["written"] == 0
    assert io.StringIO.getvalue(stream) == ""
    assert handler.close_within() is True  # a second close is harmless


def test_rejected_records_are_counted_on_the_caller_thread():
    logger, handler = logger_for(io.StringIO())
    logger.info("x", extra={"fields": {"not.allowed": object()}})
    logger.info("y" * 5000, extra={"fields": {"z": object()}})
    handler.close()
    assert handler.stats()["invalid"] + handler.stats()["written"] == 2


def test_a_zero_capacity_is_refused():
    with pytest.raises(ValueError, match="queue_capacity_must_be_positive"):
        JsonLogHandler(CONFIG, io.StringIO(), queue_capacity=0)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs os.fork")
def test_fork_restarts_writer():
    read_end, write_end = os.pipe()
    stream = os.fdopen(write_end, "w")
    logger, handler = logger_for(stream)
    logger.info("parent before fork")
    handler.flush()
    pid = os.fork()
    if pid == 0:  # child: a new queue and thread, not the parent's
        try:
            logger.info("child line")
            ok = handler.close_within() and handler.stats()["written"] == 1
        finally:
            os._exit(0 if ok else 3)
    _, status = os.waitpid(pid, 0)
    logger.info("parent after fork")
    assert handler.close_within() is True
    stream.close()
    assert os.waitstatus_to_exitcode(status) == 0
    with os.fdopen(read_end) as reader:
        messages = sorted(json.loads(line)["message"] for line in reader.read().splitlines())
    assert messages == ["child line", "parent after fork", "parent before fork"]


def test_a_blocked_stdout_at_exit_keeps_the_process_exit_code():
    """The process exits in time with its own code, never 134 (fatal error at exit)."""
    code = (
        "import logging, sys\n"
        "from onenexus_observability import LogConfig, install_handler\n"
        "def run():\n"
        "    log = logging.Logger('exit', logging.INFO)\n"
        "    install_handler(log, LogConfig('svc', 'development', 'r1'))\n"
        "    for i in range(3000): log.info('line %s', i)\n"
        "run()  # handler collected after return, writer still queued\n"
        "sys.exit(7)\n"
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    child = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    start = time.monotonic()
    try:
        returncode = child.wait(timeout=MODEL["close_timeout_ms"] / 1000 + 5)  # nobody reads stdout
    finally:
        child.kill()
        out, err = child.communicate()
    assert returncode == 7, err.decode()[-400:]
    assert time.monotonic() - start < MODEL["close_timeout_ms"] / 1000 + 3
    assert b"Fatal Python error" not in err


# --- review regressions ---------------------------------------------------------------


def _run_child(code: str, timeout: float):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    start = time.monotonic()
    try:
        returncode = child.wait(timeout=timeout)
    finally:
        child.kill()
        out, err = child.communicate()
    return returncode, time.monotonic() - start, out, err


def test_exit_uses_one_deadline_for_every_live_handler():
    """Three live handlers on a blocked stdout still exit within one close deadline."""
    code = (
        "import logging, sys\n"
        "from onenexus_observability import LogConfig, install_handler\n"
        "loggers = [logging.getLogger(f'exit-{i}') for i in range(3)]\n"
        "for i, log in enumerate(loggers):\n"
        "    log.setLevel(logging.INFO)\n"
        "    install_handler(log, LogConfig(f'svc{i}', 'development', 'r1'))\n"
        "for n in range(3000):\n"
        "    loggers[n % 3].info('line %s', n)\n"
        "sys.exit(7)\n"
    )
    returncode, elapsed, _, err = _run_child(code, timeout=20)
    assert returncode == 7, err.decode()[-400:]
    assert elapsed < MODEL["close_timeout_ms"] / 1000 + 2.5, elapsed


def test_an_error_line_survives_a_hard_exit():  # error_line_survives_hard_exit
    # A slow output (20 ms per write): without the error wait the process is gone first.
    code = (
        "import io, logging, os, sys, time\n"
        "from onenexus_observability import LogConfig, install_handler\n"
        "class Slow(io.TextIOBase):\n"
        "    def write(self, value):\n"
        "        time.sleep(0.02); sys.__stdout__.write(value); sys.__stdout__.flush(); return len(value)\n"
        "log = logging.getLogger('hard-exit'); log.setLevel(logging.INFO)\n"
        "install_handler(log, LogConfig('svc', 'development', 'r1'), stream=Slow())\n"
        "log.error('fatal: giving up')\n"
        "os._exit(1)\n"
    )
    returncode, _, out, _ = _run_child(code, timeout=20)
    assert returncode == 1
    assert [json.loads(line)["message"] for line in out.decode().splitlines()] == ["fatal: giving up"]


def test_an_error_line_waits_at_most_the_error_budget():
    stream = Gate()
    logger, handler = logger_for(stream)
    start = time.perf_counter()
    logger.error("blocked error")
    assert time.perf_counter() - start < sdk_logging.ERROR_WAIT_SECONDS + 0.05
    stream.open.set()
    assert handler.close_within() is True


def test_a_handler_that_never_logs_owns_no_thread():  # unused_logger_owns_no_writer
    before = threading.active_count()
    handlers = [JsonLogHandler(CONFIG, io.StringIO()) for _ in range(50)]
    assert threading.active_count() == before
    logger = logging.Logger("one-used", logging.INFO)
    logger.addHandler(handlers[0])
    logger.info("only this one starts a writer")
    assert threading.active_count() == before + 1
    for handler in handlers:
        handler.close()
    assert threading.active_count() == before


def test_a_cut_prefix_does_not_leave_an_empty_line(monkeypatch):
    read_end, write_end = os.pipe()
    real_write = os.write
    calls = {"n": 0}

    def flaky(fd, data):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_write(fd, data[:5])  # line 0 is cut
        if calls["n"] == 2:
            raise OSError("broken pipe")
        if calls["n"] == 3:
            return real_write(fd, data[:1])  # only the ending newline of line 0 ...
        if calls["n"] == 4:
            raise OSError("broken pipe")  # ... then line 1 fails
        return real_write(fd, data)

    monkeypatch.setattr(sdk_logging.os, "write", flaky)
    stream = os.fdopen(write_end, "w")
    logger, handler = logger_for(stream)
    for i in range(3):
        logger.info("line %s", i)
    assert handler.close_within() is True
    stream.close()
    with os.fdopen(read_end) as reader:
        parts = reader.read().split("\n")
    assert "" not in parts[1:-1]  # no empty line between the cut line and line 2
    assert json.loads(parts[1])["message"] == "line 2"


def test_close_from_inside_a_write_does_not_wait_on_itself():
    holder: dict = {}

    class Closing(io.StringIO):
        def write(self, value: str) -> int:
            start = time.monotonic()
            holder["result"] = holder["handler"].close_within()
            holder["took"] = time.monotonic() - start
            return super().write(value)

    stream = Closing()
    logger, handler = logger_for(stream)
    holder["handler"] = handler
    logger.info("closes itself")
    assert handler.close_within() in (True, False)
    assert holder["took"] < 0.5


def test_a_failing_flush_still_counts_the_line_as_written():
    class NoFlush(io.StringIO):
        def flush(self) -> None:
            raise OSError("flush failed")

    stream = NoFlush()
    logger, handler = logger_for(stream)
    logger.info("kept")
    handler.close_within()
    assert (handler.stats()["written"], handler.stats()["io_errors"]) == (1, 0)

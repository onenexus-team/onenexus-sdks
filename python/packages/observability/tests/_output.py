"""Test output that waits for the SDK's background writer (design review F2)."""

from __future__ import annotations

import io

from onenexus_observability.logging import _WRITERS, CLOSE_TIMEOUT_SECONDS


def settle() -> None:
    """Wait until every live writer has written its queued lines."""
    for writer in list(_WRITERS):
        writer.drain(CLOSE_TIMEOUT_SECONDS)


class Output(io.StringIO):
    """A StringIO whose getvalue() first lets queued lines reach it."""

    def getvalue(self) -> str:
        settle()
        return super().getvalue()

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar


ResultT = TypeVar("ResultT")


class WaitTimeoutError(TimeoutError):
    """Raised when a resource does not reach a requested state in time."""


@dataclass(frozen=True)
class WaitPolicy:
    timeout_seconds: float = 900.0
    interval_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.timeout_seconds < 0:
            raise ValueError("timeout_seconds cannot be negative")
        if self.interval_seconds < 0:
            raise ValueError("interval_seconds cannot be negative")


def wait_for_status(
    fetch: Callable[[], ResultT],
    *,
    status_of: Callable[[ResultT], str],
    target_statuses: set[str] | frozenset[str],
    policy: WaitPolicy,
    description: str,
) -> ResultT:
    normalized_targets = {status.upper() for status in target_statuses}
    if not normalized_targets:
        raise ValueError("target_statuses must not be empty")

    started_at = time.monotonic()
    last_status = "unknown"
    while True:
        result = fetch()
        last_status = status_of(result)
        if last_status.upper() in normalized_targets:
            return result

        elapsed = time.monotonic() - started_at
        if elapsed >= policy.timeout_seconds:
            expected = ", ".join(sorted(normalized_targets))
            raise WaitTimeoutError(
                f"Timed out waiting for {description} to reach {expected}; "
                f"last status was {last_status}"
            )
        time.sleep(min(policy.interval_seconds, policy.timeout_seconds - elapsed))

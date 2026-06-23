"""Core credential primitives.

Mirrors the language-agnostic design in the repository ``README.md`` and the
TypeScript ``@onenexus/sdk-core`` package, expressed in idiomatic async Python.

Interfaces are :class:`typing.Protocol` definitions (PEP 544) rather than abstract
base classes: a concrete credential or clock *satisfies* an interface structurally,
without inheriting from it. Both protocols are ``@runtime_checkable`` so tests and
defensive call sites can use :func:`isinstance`.

Design note: ``expires_at`` is an absolute timezone-aware ``datetime``, never a
relative ``expires_in``. Absolute timestamps are unambiguous across process
restarts, log records, and clock observations; relative durations are not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

#: Default preemptive refresh window. A cached token is treated as expired once it
#: is within this window of ``expires_at`` so a refresh fires before the token dies.
DEFAULT_REFRESH_LEEWAY = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class AccessToken:
    """One CAS-issued access token.

    Immutable data: no behaviour, no network calls, no refresh logic, and no grant
    metadata such as refresh token, ID token, or scopes. It carries only what a
    caller needs to authenticate against OneNexus APIs.
    """

    access_token: str
    expires_at: datetime
    token_type: str = "Bearer"


@runtime_checkable
class Clock(Protocol):
    """Skew-aware clock used by credentials to decide token expiry.

    Transports observe server time from response headers; credentials read the
    corrected clock when deciding whether a cached token is near expiry.
    """

    def server_now(self) -> datetime:
        """Return the current time corrected by the latest observed server delta."""
        ...

    def observe_server_time(self, server_date: datetime) -> None:
        """Record an authoritative server timestamp to correct for clock skew."""
        ...


class SystemClock:
    """Default :class:`Clock` backed by the system clock plus an observed delta.

    Structurally satisfies the :class:`Clock` protocol without inheriting it.
    """

    __slots__ = ("_delta",)

    def __init__(self) -> None:
        self._delta = timedelta(0)

    def server_now(self) -> datetime:
        return datetime.now(UTC) + self._delta

    def observe_server_time(self, server_date: datetime) -> None:
        if server_date.tzinfo is None:
            server_date = server_date.replace(tzinfo=UTC)
        self._delta = server_date - datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ClientContext:
    """Per-client ambient state supplied to credential resolution.

    The transport owns this context, records observed server time into its clock,
    and passes it to credentials on every :meth:`Credentials.resolve` call.
    """

    clock: Clock = field(default_factory=SystemClock)
    refresh_leeway: timedelta = DEFAULT_REFRESH_LEEWAY


def default_client_context() -> ClientContext:
    """Build a :class:`ClientContext` with a fresh :class:`SystemClock`."""
    return ClientContext(clock=SystemClock(), refresh_leeway=DEFAULT_REFRESH_LEEWAY)


@runtime_checkable
class Credentials(Protocol):
    """A source of :class:`AccessToken` values.

    Credential sources support both async and sync resolution so the same object
    can be used by async SDK clients and sync-only integrations such as
    boto3/botocore refresh callbacks. Active implementations cache,
    single-flight concurrent refreshes, and honour cancellation via the
    surrounding ``asyncio`` task on the async path. Static implementations just
    return their held value.

    Raises:
        StaleCredentialsError: when a held token is expired and this credential
            cannot refresh it itself.
        AuthenticationError: when a refresh or mint attempt is rejected by the
            authentication authority.
    """

    async def resolve(self, context: ClientContext) -> AccessToken:
        """Asynchronously return a non-expired :class:`AccessToken`."""
        ...

    def resolve_sync(self, context: ClientContext) -> AccessToken:
        """Synchronously return a non-expired :class:`AccessToken`."""
        ...


__all__ = [
    "DEFAULT_REFRESH_LEEWAY",
    "AccessToken",
    "ClientContext",
    "Clock",
    "Credentials",
    "SystemClock",
    "default_client_context",
]

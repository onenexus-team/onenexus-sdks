"""Shared test helpers: a mock OIDC server and credential test doubles."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime, timedelta

import httpx

from onenexus_sdk_core import AccessToken, ClientContext


class MockOidc:
    """A mock OIDC discovery + token endpoint backed by ``httpx.MockTransport``.

    Queue token responses (or errors) FIFO; every token request's decoded form is
    recorded on :attr:`token_requests` for assertions.
    """

    def __init__(self, issuer: str = "https://cas.test.invalid") -> None:
        self.issuer = issuer
        self.token_endpoint = f"{issuer}/token"
        self.token_requests: list[dict[str, str]] = []
        self._queue: list[tuple[str, object]] = []

    def queue_token(self, **payload: object) -> None:
        self._queue.append(("ok", payload))

    def queue_error(self, status: int, error: str, description: str | None = None) -> None:
        self._queue.append(("err", (status, error, description)))

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={"issuer": self.issuer, "token_endpoint": self.token_endpoint},
            )
        if path.endswith("/token"):
            form = dict(urllib.parse.parse_qsl(request.content.decode()))
            self.token_requests.append(form)
            if not self._queue:
                return httpx.Response(500, json={"error": "no_queued_response"})
            kind, data = self._queue.pop(0)
            if kind == "ok":
                assert isinstance(data, dict)
                return httpx.Response(200, json={"token_type": "Bearer", **data})
            status, error, description = data  # type: ignore[misc]
            body = {"error": error}
            if description is not None:
                body["error_description"] = description
            return httpx.Response(int(status), json=body)
        return httpx.Response(404)


class StaticCredentials:
    """A credential double that structurally satisfies the ``Credentials`` protocol."""

    def __init__(self, access_token: str = "static-at") -> None:
        self._token = AccessToken(
            access_token=access_token,
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        self.resolve_calls = 0

    async def resolve(self, context: ClientContext) -> AccessToken:
        self.resolve_calls += 1
        return self._token

    def resolve_sync(self, context: ClientContext) -> AccessToken:
        self.resolve_calls += 1
        return self._token


class ClockCutoffCredentials:
    """Returns a fresh token only once the context clock passes ``cutoff``.

    Models the server-clock-correction path: a stale token is served until the
    transport observes the server ``Date`` and advances the clock past the cutoff.
    """

    def __init__(self, cutoff: datetime) -> None:
        self._cutoff = cutoff
        self.resolve_calls = 0
        self._stale = AccessToken(
            access_token="at-stale", expires_at=datetime(2030, 1, 1, tzinfo=UTC)
        )
        self._fresh = AccessToken(
            access_token="at-fresh", expires_at=datetime(2030, 1, 1, tzinfo=UTC)
        )

    async def resolve(self, context: ClientContext) -> AccessToken:
        self.resolve_calls += 1
        return self._fresh if context.clock.server_now() >= self._cutoff else self._stale

    def resolve_sync(self, context: ClientContext) -> AccessToken:
        self.resolve_calls += 1
        return self._fresh if context.clock.server_now() >= self._cutoff else self._stale


def soon(seconds: int = 1) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def far_future() -> datetime:
    return datetime(2030, 1, 1, tzinfo=UTC)


def advance_clock(context: ClientContext, seconds: float) -> None:
    """Advance the context's clock by observing a future server timestamp."""
    context.clock.observe_server_time(datetime.now(UTC) + timedelta(seconds=seconds))


def rsa_private_key_pem() -> str:
    """Generate a throwaway RSA private key as PEM for signing test assertions."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")

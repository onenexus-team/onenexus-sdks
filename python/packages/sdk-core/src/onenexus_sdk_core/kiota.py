"""Kiota integration for OneNexus credentials.

Kiota-generated clients use a ``RequestAdapter`` and an authentication provider
rather than directly calling our ``ClientBase`` transport. This module is the
bridge: it adapts the OneNexus ``Credentials`` protocol to Kiota's bearer-token
provider interface, while preserving the shared ``ClientContext`` (server-clock
observation + refresh leeway).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime

import httpx
from kiota_abstractions.authentication.access_token_provider import AccessTokenProvider
from kiota_abstractions.authentication.allowed_hosts_validator import AllowedHostsValidator
from kiota_abstractions.authentication.base_bearer_token_authentication_provider import (
    BaseBearerTokenAuthenticationProvider,
)
from kiota_http.httpx_request_adapter import HttpxRequestAdapter

from .credentials.model import ClientContext, Credentials, default_client_context


class OneNexusAccessTokenProvider(AccessTokenProvider):
    """Kiota access-token provider backed by OneNexus ``Credentials``."""

    def __init__(
        self,
        credentials: Credentials,
        context: ClientContext,
        *,
        allowed_hosts: list[str] | None = None,
    ) -> None:
        self._credentials = credentials
        self._context = context
        self._allowed_hosts_validator = AllowedHostsValidator(allowed_hosts or [])

    async def get_authorization_token(
        self, uri: str, additional_authentication_context: dict[str, object] | None = None
    ) -> str:
        if not self._allowed_hosts_validator.is_url_host_valid(uri):
            return ""
        token = await self._credentials.resolve(self._context)
        return token.access_token

    def get_allowed_hosts_validator(self) -> AllowedHostsValidator:
        return self._allowed_hosts_validator


def create_kiota_request_adapter(
    *,
    base_url: str,
    credentials: Credentials,
    context: ClientContext | None = None,
    http_client: httpx.AsyncClient | None = None,
    allowed_hosts: list[str] | None = None,
) -> HttpxRequestAdapter:
    """Build a Kiota ``HttpxRequestAdapter`` wired to OneNexus credentials.

    The returned adapter uses Kiota's standard HTTPX transport and serialization
    stack, while the bearer token comes from our ``Credentials`` protocol. Server
    ``Date`` headers are observed into the supplied context's clock.
    """
    resolved_context = context or default_client_context()
    provider = BaseBearerTokenAuthenticationProvider(
        OneNexusAccessTokenProvider(credentials, resolved_context, allowed_hosts=allowed_hosts)
    )
    client = http_client or httpx.AsyncClient(
        base_url=base_url,
        event_hooks={"response": [_observe_server_date(resolved_context)]},
    )
    adapter = HttpxRequestAdapter(provider, http_client=client, base_url=base_url)
    adapter.base_url = base_url
    return adapter


def _observe_server_date(context: ClientContext) -> Callable[[httpx.Response], Awaitable[None]]:
    async def hook(response: httpx.Response) -> None:
        header = response.headers.get("date")
        if header is None:
            return
        try:
            server_date = parsedate_to_datetime(header)
        except (TypeError, ValueError):
            return
        context.clock.observe_server_time(server_date)

    return hook


__all__ = ["OneNexusAccessTokenProvider", "create_kiota_request_adapter"]

"""Credentials backed by an externally obtained token grant."""

from __future__ import annotations

import asyncio
import threading
from datetime import timedelta
from typing import Any

import httpx

from . import _oidc
from .errors import StaleCredentialsError
from .model import AccessToken, ClientContext


class TokenGrantCredentials:
    """Credentials seeded with a token grant obtained out-of-band.

    Useful when the application already holds a grant from CAS or an external
    login library and wants to feed it into a service client. When refresh-token
    grant settings (``refresh_token`` plus ``client_id`` and an ``issuer`` or
    ``server_metadata``) are supplied, this credential refreshes transparently as
    the access token nears expiry. Otherwise an expired token raises
    :class:`StaleCredentialsError`.

    Structurally satisfies the :class:`Credentials` protocol.
    """

    def __init__(
        self,
        *,
        token: AccessToken,
        refresh_token: str | None = None,
        id_token: str | None = None,
        scopes: tuple[str, ...] = (),
        issuer: str | None = None,
        client_id: str | None = None,
        server_metadata: _oidc.ServerMetadata | None = None,
        refresh_leeway: timedelta | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sync_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._cached = token
        self._refresh_token = refresh_token
        self._id_token = id_token
        self._scopes = scopes
        self._issuer = issuer
        self._client_id = client_id
        self._server_metadata = server_metadata
        self._refresh_leeway = refresh_leeway
        self._transport = transport
        self._sync_transport = sync_transport
        self._lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    @property
    def id_token(self) -> str | None:
        return self._id_token

    @property
    def scopes(self) -> tuple[str, ...]:
        return self._scopes

    async def resolve(self, context: ClientContext) -> AccessToken:
        leeway = (
            self._refresh_leeway if self._refresh_leeway is not None else context.refresh_leeway
        )
        if not _oidc.is_near_expiry(self._cached, context.clock, leeway):
            return self._cached

        async with self._lock:
            if not _oidc.is_near_expiry(self._cached, context.clock, leeway):
                return self._cached
            if not self._can_refresh():
                raise StaleCredentialsError(
                    "TokenGrantCredentials: access token is stale and no "
                    "refresh-token grant is configured."
                )
            self._cached = await self._refresh(context)
            return self._cached

    def resolve_sync(self, context: ClientContext) -> AccessToken:
        leeway = (
            self._refresh_leeway if self._refresh_leeway is not None else context.refresh_leeway
        )
        if not _oidc.is_near_expiry(self._cached, context.clock, leeway):
            return self._cached

        with self._sync_lock:
            if not _oidc.is_near_expiry(self._cached, context.clock, leeway):
                return self._cached
            if not self._can_refresh():
                raise StaleCredentialsError(
                    "TokenGrantCredentials: access token is stale and no "
                    "refresh-token grant is configured."
                )
            self._cached = self._refresh_sync(context)
            return self._cached

    def _can_refresh(self) -> bool:
        return (
            self._refresh_token is not None
            and self._client_id is not None
            and (self._issuer is not None or self._server_metadata is not None)
        )

    async def _refresh(self, context: ClientContext) -> AccessToken:
        async with httpx.AsyncClient(transport=self._transport) as http:
            metadata = await self._resolve_metadata(http)
            payload = await _oidc.request_token(
                http,
                metadata.token_endpoint,
                self._build_refresh_form(),
            )
        return self._apply_token_payload(payload, context)

    def _refresh_sync(self, context: ClientContext) -> AccessToken:
        with httpx.Client(transport=self._sync_transport) as http:
            metadata = self._resolve_metadata_sync(http)
            payload = _oidc.request_token_sync(
                http,
                metadata.token_endpoint,
                self._build_refresh_form(),
            )
        return self._apply_token_payload(payload, context)

    def _build_refresh_form(self) -> dict[str, str]:
        assert self._refresh_token is not None and self._client_id is not None
        return {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
        }

    def _apply_token_payload(self, payload: dict[str, Any], context: ClientContext) -> AccessToken:
        rotated = payload.get("refresh_token")
        if isinstance(rotated, str):
            self._refresh_token = rotated
        id_token = payload.get("id_token")
        if isinstance(id_token, str):
            self._id_token = id_token
        scope = payload.get("scope")
        if isinstance(scope, str):
            self._scopes = tuple(scope.split())
        return _oidc.to_access_token(payload, context.clock)

    async def _resolve_metadata(self, http: httpx.AsyncClient) -> _oidc.ServerMetadata:
        if self._server_metadata is None:
            assert self._issuer is not None
            self._server_metadata = await _oidc.discover(http, self._issuer)
        return self._server_metadata

    def _resolve_metadata_sync(self, http: httpx.Client) -> _oidc.ServerMetadata:
        if self._server_metadata is None:
            assert self._issuer is not None
            self._server_metadata = _oidc.discover_sync(http, self._issuer)
        return self._server_metadata


__all__ = ["TokenGrantCredentials"]

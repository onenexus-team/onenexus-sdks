"""Private-key JWT (client assertion) credentials — scenario 3.1b."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import httpx

from . import _oidc
from .model import AccessToken, ClientContext


class PrivateKeyJwtCredentials:
    """Client Credentials grant authenticated with a ``private_key_jwt`` assertion.

    The customer's backend signs short-lived client-assertion JWTs with the
    private key registered at CAS; CAS validates them against the matching public
    key. The resulting access token is cached until shortly before expiry, and
    concurrent :meth:`resolve` calls during a refresh share one in-flight request
    (single-flight).

    Structurally satisfies the :class:`Credentials` protocol.
    """

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        signing_key: Any,
        signing_key_id: str,
        audience: str | None = None,
        scopes: tuple[str, ...] = (),
        signing_algorithm: str = "RS256",
        server_metadata: _oidc.ServerMetadata | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sync_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._issuer = issuer
        self._client_id = client_id
        self._signing_key = signing_key
        self._signing_key_id = signing_key_id
        self._audience = audience
        self._scopes = scopes
        self._signing_algorithm = signing_algorithm
        self._server_metadata = server_metadata
        self._transport = transport
        self._sync_transport = sync_transport
        self._cached: AccessToken | None = None
        self._lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    async def resolve(self, context: ClientContext) -> AccessToken:
        cached = self._cached
        if cached is not None and not _oidc.is_near_expiry(
            cached, context.clock, context.refresh_leeway
        ):
            return cached

        async with self._lock:
            cached = self._cached
            if cached is not None and not _oidc.is_near_expiry(
                cached, context.clock, context.refresh_leeway
            ):
                return cached
            token = await self._mint(context)
            self._cached = token
            return token

    def resolve_sync(self, context: ClientContext) -> AccessToken:
        cached = self._cached
        if cached is not None and not _oidc.is_near_expiry(
            cached, context.clock, context.refresh_leeway
        ):
            return cached

        with self._sync_lock:
            cached = self._cached
            if cached is not None and not _oidc.is_near_expiry(
                cached, context.clock, context.refresh_leeway
            ):
                return cached
            token = self._mint_sync(context)
            self._cached = token
            return token

    async def _mint(self, context: ClientContext) -> AccessToken:
        form = self._build_token_form()
        async with httpx.AsyncClient(transport=self._transport) as http:
            metadata = await self._resolve_metadata(http)
            payload = await _oidc.request_token(http, metadata.token_endpoint, form)
        return _oidc.to_access_token(payload, context.clock)

    def _mint_sync(self, context: ClientContext) -> AccessToken:
        form = self._build_token_form()
        with httpx.Client(transport=self._sync_transport) as http:
            metadata = self._resolve_metadata_sync(http)
            payload = _oidc.request_token_sync(http, metadata.token_endpoint, form)
        return _oidc.to_access_token(payload, context.clock)

    def _build_token_form(self) -> dict[str, str]:
        assertion = _oidc.build_client_assertion(
            issuer=self._issuer,
            client_id=self._client_id,
            signing_key=self._signing_key,
            signing_key_id=self._signing_key_id,
            algorithm=self._signing_algorithm,
        )
        form = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_assertion_type": _oidc.JWT_BEARER_ASSERTION_TYPE,
            "client_assertion": assertion,
        }
        if self._audience is not None:
            form["audience"] = self._audience
        if self._scopes:
            form["scope"] = " ".join(self._scopes)
        return form

    async def _resolve_metadata(self, http: httpx.AsyncClient) -> _oidc.ServerMetadata:
        if self._server_metadata is None:
            self._server_metadata = await _oidc.discover(http, self._issuer)
        return self._server_metadata

    def _resolve_metadata_sync(self, http: httpx.Client) -> _oidc.ServerMetadata:
        if self._server_metadata is None:
            self._server_metadata = _oidc.discover_sync(http, self._issuer)
        return self._server_metadata


__all__ = ["PrivateKeyJwtCredentials"]

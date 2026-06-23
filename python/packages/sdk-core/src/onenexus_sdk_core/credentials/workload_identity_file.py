"""Web-identity file credentials — federated workload-to-platform tokens.

Runtime-agnostic by design: the credential knows only about *a file that
contains a token*. It does not reference Kubernetes, projected ServiceAccount
tokens, or any other runtime concept. A workload running inside the OneNexus
platform points this credential at whatever file its runtime mounts (on
Kubernetes that is the projected ServiceAccount token), and CAS exchanges that
token for a CAS access token.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import httpx

from . import _oidc
from .model import AccessToken, ClientContext

#: Custom OAuth grant type CAS recognises for the workload-identity file exchange.
#: The workload presents the file token as ``subject_token`` with
#: :data:`WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE`, and CAS mints a CAS access token in
#: return.
WORKLOAD_IDENTITY_GRANT_TYPE = "urn:onenexus:params:oauth:grant-type:workload-identity"

#: Custom ``subject_token_type`` value for workload-identity file tokens.
WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:jwt"

#: Neutral default mount path for the workload-identity token. Platform deployments
#: project their runtime identity token to this path; on Kubernetes that is a
#: projected ServiceAccount token volume mounted here.
DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH = "/var/run/secrets/onenexus/token"  # noqa: S105


class WorkloadIdentityFileCredentials:
    """Exchange a file-mounted identity token for a CAS access token.

    On each mint, reads the token from :attr:`token_path` on disk and presents
    it to CAS under the :data:`WORKLOAD_IDENTITY_GRANT_TYPE` grant. The resulting CAS
    access token is cached until shortly before expiry; concurrent
    :meth:`resolve` calls during a refresh share one in-flight request
    (single-flight).

    The token file is re-read on every mint because the runtime rotates the
    projection in place; caching the file token in memory would risk presenting
    a stale one after rotation.

    Structurally satisfies the :class:`Credentials` protocol.
    """

    def __init__(
        self,
        *,
        issuer: str,
        token_path: str = DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH,
        client_id: str | None = None,
        audience: str | None = None,
        scopes: tuple[str, ...] = (),
        server_metadata: _oidc.ServerMetadata | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sync_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._issuer = issuer
        self._token_path = Path(token_path)
        self._client_id = client_id or None
        self._audience = audience
        self._scopes = scopes
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
        """Synchronously return a non-expired CAS access token.

        This is intended for sync-only integration points like boto3/botocore.
        Async applications should use :meth:`resolve`.
        """
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
        identity_token = await asyncio.to_thread(self._read_identity_token)
        form = {
            "grant_type": WORKLOAD_IDENTITY_GRANT_TYPE,
            "subject_token": identity_token,
            "subject_token_type": WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE,
        }
        if self._client_id is not None:
            form["client_id"] = self._client_id
        if self._audience is not None:
            form["audience"] = self._audience
        if self._scopes:
            form["scope"] = " ".join(self._scopes)

        async with httpx.AsyncClient(transport=self._transport) as http:
            metadata = await self._resolve_metadata(http)
            payload = await _oidc.request_token(http, metadata.token_endpoint, form)
        return _oidc.to_access_token(payload, context.clock)

    def _mint_sync(self, context: ClientContext) -> AccessToken:
        identity_token = self._read_identity_token()
        form = {
            "grant_type": WORKLOAD_IDENTITY_GRANT_TYPE,
            "subject_token": identity_token,
            "subject_token_type": WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE,
        }
        if self._client_id is not None:
            form["client_id"] = self._client_id
        if self._audience is not None:
            form["audience"] = self._audience
        if self._scopes:
            form["scope"] = " ".join(self._scopes)

        with httpx.Client(transport=self._sync_transport) as http:
            metadata = self._resolve_metadata_sync(http)
            payload = _oidc.request_token_sync(http, metadata.token_endpoint, form)
        return _oidc.to_access_token(payload, context.clock)

    def _read_identity_token(self) -> str:
        return self._token_path.read_text(encoding="utf-8").strip()

    async def _resolve_metadata(self, http: httpx.AsyncClient) -> _oidc.ServerMetadata:
        if self._server_metadata is None:
            self._server_metadata = await _oidc.discover(http, self._issuer)
        return self._server_metadata

    def _resolve_metadata_sync(self, http: httpx.Client) -> _oidc.ServerMetadata:
        if self._server_metadata is None:
            self._server_metadata = _oidc.discover_sync(http, self._issuer)
        return self._server_metadata


__all__ = [
    "DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH",
    "WORKLOAD_IDENTITY_GRANT_TYPE",
    "WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE",
    "WorkloadIdentityFileCredentials",
]

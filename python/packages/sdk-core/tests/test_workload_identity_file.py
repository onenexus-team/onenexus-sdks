from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from helpers import MockOidc
from onenexus_sdk_core import (
    WORKLOAD_IDENTITY_GRANT_TYPE,
    WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE,
    ClientContext,
    Credentials,
    SystemClock,
    WorkloadIdentityFileCredentials,
)


def _context() -> ClientContext:
    return ClientContext(clock=SystemClock(), refresh_leeway=timedelta(seconds=30))


def _creds(
    mock: MockOidc, token_path: Path, **kwargs: object
) -> WorkloadIdentityFileCredentials:
    return WorkloadIdentityFileCredentials(
        issuer=mock.issuer,
        token_path=str(token_path),
        transport=mock.transport(),
        sync_transport=mock.transport(),
        **kwargs,  # type: ignore[arg-type]
    )


def test_satisfies_credentials_protocol(tmp_path: Path) -> None:
    mock = MockOidc()
    token_file = tmp_path / "token"
    token_file.write_text("file-token")
    assert isinstance(_creds(mock, token_file), Credentials)


async def test_presents_file_token_under_workload_identity_grant(tmp_path: Path) -> None:
    mock = MockOidc()
    mock.queue_token(access_token="wif-at-1", expires_in=3600)
    token_file = tmp_path / "token"
    token_file.write_text("initial-file-token\n")
    creds = _creds(
        mock,
        token_file,
        client_id="notebook-runner",
        audience="datastore-api",
        scopes=("datastore:read",),
    )

    token = await creds.resolve(_context())

    assert token.access_token == "wif-at-1"
    form = mock.token_requests[0]
    assert form["grant_type"] == WORKLOAD_IDENTITY_GRANT_TYPE
    assert form["client_id"] == "notebook-runner"
    assert form["subject_token"] == "initial-file-token"
    assert form["subject_token_type"] == WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE
    assert form["audience"] == "datastore-api"
    assert form["scope"] == "datastore:read"


async def test_omits_client_id_by_default(tmp_path: Path) -> None:
    mock = MockOidc()
    mock.queue_token(access_token="wif-at-default", expires_in=3600)
    token_file = tmp_path / "token"
    token_file.write_text("file-token")
    creds = _creds(mock, token_file)

    await creds.resolve(_context())

    form = mock.token_requests[0]
    assert "client_id" not in form
    assert "audience" not in form
    assert "scope" not in form


def test_resolve_sync_presents_file_token_under_workload_identity_grant(tmp_path: Path) -> None:
    mock = MockOidc()
    mock.queue_token(access_token="wif-sync", expires_in=3600)
    token_file = tmp_path / "token"
    token_file.write_text("sync-file-token\n")
    creds = _creds(mock, token_file, client_id="notebook-runner")

    token = creds.resolve_sync(_context())

    assert token.access_token == "wif-sync"
    form = mock.token_requests[0]
    assert form["grant_type"] == WORKLOAD_IDENTITY_GRANT_TYPE
    assert form["client_id"] == "notebook-runner"
    assert form["subject_token"] == "sync-file-token"
    assert form["subject_token_type"] == WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE


async def test_caches_token_across_resolves(tmp_path: Path) -> None:
    mock = MockOidc()
    mock.queue_token(access_token="wif-cached", expires_in=3600)
    token_file = tmp_path / "token"
    token_file.write_text("file-token")
    creds = _creds(mock, token_file)
    context = _context()

    first = await creds.resolve(context)
    second = await creds.resolve(context)

    assert first is second
    assert len(mock.token_requests) == 1


async def test_rereads_token_file_on_each_mint(tmp_path: Path) -> None:
    mock = MockOidc()
    mock.queue_token(access_token="wif-at-first", expires_in=3600)
    mock.queue_token(access_token="wif-at-second", expires_in=3600)
    token_file = tmp_path / "token"
    token_file.write_text("rotated-token-1")
    creds = _creds(mock, token_file)
    context = _context()

    first = await creds.resolve(context)

    # Rotate the projected token on disk, then force a fresh mint.
    token_file.write_text("rotated-token-2")
    context.clock.observe_server_time(context.clock.server_now() + timedelta(hours=2))
    second = await creds.resolve(context)

    assert first.access_token == "wif-at-first"
    assert second.access_token == "wif-at-second"
    assert mock.token_requests[0]["subject_token"] == "rotated-token-1"
    assert mock.token_requests[1]["subject_token"] == "rotated-token-2"

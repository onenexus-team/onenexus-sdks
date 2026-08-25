from __future__ import annotations

import json
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from onenexus_sdk_core import AccessToken

from nexusai import OneNexusClient
from nexusai import auth
from nexusai.auth import CredentialLogin
from nexusai.cli import build_parser
from nexusai.cli_handlers import handle_login, handle_whoami
from nexusai.config import CAS_BASE_URL, PLATFORM_BASE_URL


def _configure_auth_paths(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(auth, "CONFIG_DIR", root)
    monkeypatch.setattr(auth, "TOKEN_FILE", root / "token")
    monkeypatch.setattr(auth, "API_URL_FILE", root / "api_url")
    monkeypatch.setattr(auth, "CAS_URL_FILE", root / "cas_url")
    monkeypatch.setattr(auth, "CREDENTIAL_LOGIN_FILE", root / "credential_login.json")


def test_credential_login_parser_accepts_private_key_jwt_options() -> None:
    args = build_parser().parse_args(
        [
            "login",
            "--client-id",
            "client-1",
            "--key-id",
            "key-1",
            "--credential-file",
            "/tmp/private.pem",
        ]
    )

    assert args.client_id == "client-1"
    assert args.key_id == "key-1"
    assert args.credential_file == "/tmp/private.pem"


def test_v3_and_global_auth_are_the_default_endpoints() -> None:
    assert PLATFORM_BASE_URL == "https://ai-api-v3.ric1.onenexus-do.cloud"
    assert CAS_BASE_URL == "https://auth.onenexus-do.cloud"


def test_save_credential_login_persists_metadata_not_private_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    private_key = tmp_path / "private.pem"
    private_key.write_text("private-key-material")
    private_key.chmod(0o600)
    _configure_auth_paths(monkeypatch, config_dir)

    saved = auth.save_credential_login(
        client_id="client-1",
        key_id="key-1",
        credential_file=str(private_key),
        api_url="https://api.example.test",
        cas_url="https://cas.example.test",
    )

    payload = json.loads((config_dir / "credential_login.json").read_text())
    assert saved == CredentialLogin("client-1", "key-1", str(private_key))
    assert payload == {
        "client_id": "client-1",
        "key_id": "key-1",
        "credential_file": str(private_key),
    }
    assert "private-key-material" not in json.dumps(payload)
    assert (config_dir / "credential_login.json").stat().st_mode & 0o777 == 0o600


def test_credential_login_rejects_world_readable_private_key(tmp_path: Path) -> None:
    private_key = tmp_path / "private.pem"
    private_key.write_text("private-key-material")
    private_key.chmod(0o644)

    with pytest.raises(ValueError, match="chmod 600"):
        auth.create_private_key_jwt_credentials(
            CredentialLogin("client-1", "key-1", str(private_key)),
            cas_url="https://cas.example.test",
        )


def test_handle_login_verifies_and_saves_client_credential() -> None:
    token = _fake_jwt({"client_id": "client-1", "exp": 1_893_456_000})
    credentials = SimpleNamespace(
        resolve_sync=lambda _context: AccessToken(
            access_token=token,
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
    )
    args = Namespace(
        token=None,
        url="https://api.example.test",
        base_url=None,
        cas_url="https://cas.example.test",
        client_id="client-1",
        key_id="key-1",
        credential_file="/private.pem",
    )

    with (
        patch(
            "nexusai.cli_handlers.create_private_key_jwt_credentials",
            return_value=credentials,
        ),
        patch("nexusai.cli_handlers.save_credential_login") as save_login,
    ):
        result = handle_login(args)

    assert result["logged_in"] is True
    assert result["authentication_method"] == "private_key_jwt"
    assert result["client_id"] == "client-1"
    save_login.assert_called_once_with(
        client_id="client-1",
        key_id="key-1",
        credential_file="/private.pem",
        api_url="https://api.example.test",
        cas_url="https://cas.example.test",
    )


def test_whoami_mints_fresh_token_for_saved_credential() -> None:
    token = _fake_jwt({"client_id": "client-1", "exp": 1_893_456_000})
    credentials = SimpleNamespace(
        resolve_sync=lambda _context: AccessToken(
            access_token=token,
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
    )
    args = Namespace(token=None, base_url=None, cas_url=None)

    with (
        patch("nexusai.cli_handlers.load_token", return_value=None),
        patch(
            "nexusai.cli_handlers.load_credential_login",
            return_value=CredentialLogin("client-1", "key-1", "/private.pem"),
        ),
        patch(
            "nexusai.cli_handlers.create_private_key_jwt_credentials",
            return_value=credentials,
        ),
        patch("nexusai.cli_handlers.load_api_url", return_value="https://api.test"),
        patch("nexusai.cli_handlers.load_cas_url", return_value="https://cas.test"),
    ):
        result = handle_whoami(args)

    assert result["logged_in"] is True
    assert result["authentication_method"] == "private_key_jwt"
    assert result["client_id"] == "client-1"


def test_public_client_accepts_refreshable_credentials() -> None:
    credentials = SimpleNamespace(resolve=object(), resolve_sync=object())

    client = OneNexusClient.from_credentials(credentials)  # type: ignore[arg-type]

    assert client.token is None
    assert client._credentials is credentials


def _fake_jwt(payload: dict[str, object]) -> str:
    import base64

    def encode(value: dict[str, object]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode(payload)}.signature"

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from onenexus_sdk_core import AccessToken

from nexusai.client import OneNexusClient
from nexusai.http import APIClient
from nexusai import workload_auth


class RotatingCredentials:
    def __init__(self) -> None:
        self.resolve_count = 0

    def resolve_sync(self, _context):
        self.resolve_count += 1
        return AccessToken(
            access_token=f"token-{self.resolve_count}",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


def test_api_client_resolves_credentials_for_every_request() -> None:
    credentials = RotatingCredentials()
    client = APIClient(
        credentials=credentials,
        base_url="https://api.example.test",
    )

    assert client._authorization_header() == "Bearer token-1"
    assert client._authorization_header() == "Bearer token-2"


def test_create_private_key_jwt_credentials_loads_jwk(
    monkeypatch,
    tmp_path,
) -> None:
    private_jwk = {
        "kty": "EC",
        "d": "private-material",
        "kid": "key-1",
        "alg": "ES256",
    }
    jwk_path = tmp_path / "private-jwk.json"
    jwk_path.write_text(json.dumps(private_jwk), encoding="utf-8")
    signing_key = object()
    constructed = object()
    captured = {}

    monkeypatch.setattr(
        workload_auth.jwt.PyJWK,
        "from_dict",
        lambda value: SimpleNamespace(key=signing_key),
    )

    def fake_credentials(**kwargs):
        captured.update(kwargs)
        return constructed

    monkeypatch.setattr(
        workload_auth,
        "PrivateKeyJwtCredentials",
        fake_credentials,
    )

    result = workload_auth.create_private_key_jwt_credentials(
        issuer="https://cas.example.test/",
        client_id="workload-client",
        private_jwk_path=str(jwk_path),
    )

    assert result is constructed
    assert captured == {
        "issuer": "https://cas.example.test",
        "client_id": "workload-client",
        "signing_key": signing_key,
        "signing_key_id": "key-1",
        "signing_algorithm": "ES256",
    }


@pytest.mark.parametrize(
    "content, message",
    [
        ("not-json", "valid JSON"),
        (json.dumps({"kid": "key-1"}), "private material"),
    ],
)
def test_create_private_key_jwt_credentials_rejects_invalid_jwk(
    tmp_path,
    content: str,
    message: str,
) -> None:
    jwk_path = tmp_path / "private-jwk.json"
    jwk_path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        workload_auth.create_private_key_jwt_credentials(
            issuer="https://cas.example.test",
            client_id="workload-client",
            private_jwk_path=str(jwk_path),
        )


def test_create_workload_client_wires_refreshable_credentials(monkeypatch) -> None:
    credentials = RotatingCredentials()
    expected_client = object()
    captured = {}

    monkeypatch.setattr(
        workload_auth,
        "create_private_key_jwt_credentials",
        lambda **_kwargs: credentials,
    )

    def fake_from_credentials(cls, resolved_credentials, **kwargs):
        captured["credentials"] = resolved_credentials
        captured.update(kwargs)
        return expected_client

    monkeypatch.setattr(
        OneNexusClient,
        "_from_credentials",
        classmethod(fake_from_credentials),
    )

    result = workload_auth.create_workload_client(
        client_id="workload-client",
        private_jwk_path="/var/run/private-jwk.json",
        base_url="https://api.example.test",
        cas_url="https://cas.example.test",
        s3_endpoint_url="https://s3.example.test",
        s3_role_name="S3Role",
        timeout=23,
    )

    assert result is expected_client
    assert captured == {
        "credentials": credentials,
        "base_url": "https://api.example.test",
        "cas_url": "https://cas.example.test",
        "s3_endpoint_url": "https://s3.example.test",
        "s3_role_name": "S3Role",
        "timeout": 23,
    }

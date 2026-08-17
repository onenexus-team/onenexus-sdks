from __future__ import annotations

import base64
import datetime
import json
import urllib.parse

import httpx
import pytest
from onenexus_cas_client import AssumeS3RoleResponse
from onenexus_sdk_core import AccessToken, ClientContext, PrivateKeyJwtCredentials

from onenexus_boto3.credentials import (
    OneNexusBoto3Bridge,
    WorkloadIdentityS3Credentials,
    _to_botocore_metadata,
)


class SyncStaticCredentials:
    def __init__(self, access_token: str = "cas-at") -> None:
        self.resolve_sync_calls = 0
        self._token = AccessToken(
            access_token=access_token,
            expires_at=datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC),
        )

    async def resolve(self, context: ClientContext) -> AccessToken:
        return self.resolve_sync(context)

    def resolve_sync(self, context: ClientContext) -> AccessToken:
        self.resolve_sync_calls += 1
        return self._token


def _unsigned_access_token(issuer: str) -> str:
    def encode(value: dict[str, str]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{encode({'alg': 'ES256'})}.{encode({'iss': issuer})}.signature"


def test_to_botocore_metadata_maps_all_fields() -> None:
    expiry = datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC)
    response = AssumeS3RoleResponse(
        access_key_id="AKIAEXAMPLE",
        secret_access_key="secret",
        session_token="session-token",
        expiration=expiry,
    )

    metadata = _to_botocore_metadata(response)

    assert metadata == {
        "access_key": "AKIAEXAMPLE",
        "secret_key": "secret",
        "token": "session-token",
        "expiry_time": expiry.isoformat(),
    }


@pytest.mark.parametrize(
    "override",
    [
        {"access_key_id": None},
        {"secret_access_key": None},
        {"session_token": None},
        {"expiration": None},
    ],
)
def test_to_botocore_metadata_rejects_incomplete(override: dict[str, object]) -> None:
    fields: dict[str, object] = {
        "access_key_id": "AKIAEXAMPLE",
        "secret_access_key": "secret",
        "session_token": "session-token",
        "expiration": datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC),
    }
    fields.update(override)
    response = AssumeS3RoleResponse(**fields)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError):
        _to_botocore_metadata(response)


def test_refresh_uses_sync_credentials_and_sync_assume_s3_role() -> None:
    credentials = SyncStaticCredentials()
    requests: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "path": request.url.path,
                "authorization": request.headers.get("authorization"),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json={
                "accessKeyId": "AKIAEXAMPLE",
                "secretAccessKey": "secret",
                "sessionToken": "session-token",
                "expiration": "2030-01-01T00:00:00+00:00",
            },
        )

    bridge_credentials = WorkloadIdentityS3Credentials(
        cas_base_url="https://auth.test.invalid",
        role_name="S3ObjectFullAccess",
        credentials=credentials,
        s3_endpoint_url="https://s3.test.invalid",
        transport=httpx.MockTransport(handle),
    )

    metadata = bridge_credentials.refreshable_credentials.get_frozen_credentials()

    assert metadata.access_key == "AKIAEXAMPLE"
    assert metadata.secret_key == "secret"
    assert metadata.token == "session-token"
    assert credentials.resolve_sync_calls == 1
    assert requests == [
        {
            "path": "/api/AssumeS3Role",
            "authorization": "Bearer cas-at",
            "body": {"roleName": "S3ObjectFullAccess"},
        }
    ]


def test_refresh_routes_regional_workload_token_to_its_issuer() -> None:
    requests: list[tuple[str, str | None]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append((str(request.url), request.headers.get("authorization")))
        return httpx.Response(
            200,
            json={
                "accessKeyId": "AKIAEXAMPLE",
                "secretAccessKey": "secret",
                "sessionToken": "session-token",
                "expiration": "2030-01-01T00:00:00+00:00",
            },
        )

    access_token = _unsigned_access_token("https://auth.ric1.onenexus.test")
    credentials = SyncStaticCredentials(access_token)
    bridge_credentials = WorkloadIdentityS3Credentials(
        cas_base_url="https://auth.onenexus.test",
        role_name="S3ObjectFullAccess",
        credentials=credentials,
        s3_endpoint_url="https://s3.ric1.onenexus.test",
        transport=httpx.MockTransport(handle),
    )

    bridge_credentials.refreshable_credentials.get_frozen_credentials()

    assert requests == [
        ("https://auth.ric1.onenexus.test/api/AssumeS3Role", f"Bearer {access_token}")
    ]


def test_private_key_jwt_credentials_can_back_s3_bridge() -> None:
    requests: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://auth.test.invalid",
                    "token_endpoint": "https://auth.test.invalid/token",
                },
            )
        if request.url.path.endswith("/token"):
            form = dict(urllib.parse.parse_qsl(request.content.decode()))
            requests.append({"path": request.url.path, "body": form})
            return httpx.Response(200, json={"access_token": "cas-at", "expires_in": 3600})
        if request.url.path == "/api/AssumeS3Role":
            requests.append(
                {
                    "path": request.url.path,
                    "authorization": request.headers.get("authorization"),
                    "body": json.loads(request.content),
                }
            )
            return httpx.Response(
                200,
                json={
                    "accessKeyId": "AKIAEXAMPLE",
                    "secretAccessKey": "secret",
                    "sessionToken": "session-token",
                    "expiration": "2030-01-01T00:00:00+00:00",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handle)
    credentials = PrivateKeyJwtCredentials(
        issuer="https://auth.test.invalid",
        client_id="acme-batch",
        signing_key=_rsa_private_key_pem(),
        signing_key_id="acme-2026",
        sync_transport=transport,
    )

    bridge_credentials = WorkloadIdentityS3Credentials(
        cas_base_url="https://auth.test.invalid",
        role_name="S3ObjectFullAccess",
        credentials=credentials,
        s3_endpoint_url="https://s3.test.invalid",
        transport=transport,
    )

    metadata = bridge_credentials.refreshable_credentials.get_frozen_credentials()

    assert metadata.access_key == "AKIAEXAMPLE"
    token_request = requests[0]
    assert token_request["path"] == "/token"
    assert isinstance(token_request["body"], dict)
    assert token_request["body"]["grant_type"] == "client_credentials"
    assert token_request["body"]["client_id"] == "acme-batch"
    assert token_request["body"]["client_assertion"]
    assert requests[1] == {
        "path": "/api/AssumeS3Role",
        "authorization": "Bearer cas-at",
        "body": {"roleName": "S3ObjectFullAccess"},
    }


def test_create_s3_client_uses_credentials_endpoint_and_region() -> None:
    credentials = SyncStaticCredentials()

    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "accessKeyId": "AKIAEXAMPLE",
                "secretAccessKey": "secret",
                "sessionToken": "session-token",
                "expiration": "2030-01-01T00:00:00+00:00",
            },
        )

    bridge_credentials = WorkloadIdentityS3Credentials(
        cas_base_url="https://auth.test.invalid",
        role_name="S3ObjectFullAccess",
        credentials=credentials,
        s3_endpoint_url="https://s3.test.invalid",
        s3_region_name="us-test-1",
        transport=httpx.MockTransport(handle),
    )

    s3 = OneNexusBoto3Bridge.create_s3_client(bridge_credentials)

    assert s3.meta.endpoint_url == "https://s3.test.invalid"
    assert s3.meta.region_name == "us-test-1"


def _rsa_private_key_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")

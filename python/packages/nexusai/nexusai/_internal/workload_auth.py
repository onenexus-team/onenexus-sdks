from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jwt
from onenexus_sdk_core import Credentials, PrivateKeyJwtCredentials

from ..client import OneNexusClient
from ..config import (
    CAS_BASE_URL,
    CAS_S3_ROLE_NAME,
    PLATFORM_API_BASE_URL,
    S3_ENDPOINT_URL,
)


def create_private_key_jwt_credentials(
    *,
    issuer: str,
    client_id: str,
    private_jwk_path: str,
) -> Credentials:
    jwk = _load_private_jwk(private_jwk_path)
    return PrivateKeyJwtCredentials(
        issuer=issuer.rstrip("/"),
        client_id=client_id,
        signing_key=jwt.PyJWK.from_dict(jwk).key,
        signing_key_id=str(jwk["kid"]),
        signing_algorithm=str(jwk.get("alg", "ES256")),
    )


def create_workload_client(
    *,
    client_id: str,
    private_jwk_path: str,
    base_url: str = PLATFORM_API_BASE_URL,
    cas_url: str = CAS_BASE_URL,
    s3_endpoint_url: str = S3_ENDPOINT_URL,
    s3_role_name: str = CAS_S3_ROLE_NAME,
    timeout: float = 60.0,
) -> OneNexusClient:
    credentials = create_private_key_jwt_credentials(
        issuer=cas_url,
        client_id=client_id,
        private_jwk_path=private_jwk_path,
    )
    return OneNexusClient._from_credentials(
        credentials,
        base_url=base_url,
        cas_url=cas_url,
        s3_endpoint_url=s3_endpoint_url,
        s3_role_name=s3_role_name,
        timeout=timeout,
    )


def _load_private_jwk(private_jwk_path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(private_jwk_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("private JWK file must contain valid JSON") from error
    if not isinstance(value, dict) or not value.get("d") or not value.get("kid"):
        raise ValueError("private JWK must include private material and kid")
    return value


__all__ = [
    "create_private_key_jwt_credentials",
    "create_workload_client",
]

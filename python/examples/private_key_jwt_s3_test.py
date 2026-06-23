from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx
import jwt
from botocore.config import Config
from onenexus_boto3 import OneNexusBoto3Bridge, WorkloadIdentityS3Credentials
from onenexus_sdk_core import PrivateKeyJwtCredentials, default_client_context

DEFAULT_CAS_BASE_URL = "https://cas.onenexus-do.cloud"
DEFAULT_S3_ENDPOINT_URL = "https://s3.onenexus-do.cloud"
DEFAULT_CLIENT_ID = "019eee64e6697778a21a5f7ae95005b6"
DEFAULT_PRIVATE_JWK_PATH = Path(__file__).resolve().parents[3] / "private-jwt-test.json"
DEFAULT_ROLE_NAME = "S3ObjectFullAccess"
DEFAULT_REGION = "us-east-1"


def main() -> None:
    args = parse_args()
    private_jwk = load_private_jwk(args.private_jwk)
    verify: bool | str = not args.insecure
    cas_transport = httpx.HTTPTransport(verify=verify)

    cas_credentials = PrivateKeyJwtCredentials(
        issuer=args.cas_base_url,
        client_id=args.client_id,
        signing_key=jwt.PyJWK.from_dict(private_jwk).key,
        signing_key_id=str(private_jwk["kid"]),
        signing_algorithm=str(private_jwk.get("alg", "ES256")),
        sync_transport=cas_transport,
    )

    # Resolve once up front so the program explicitly verifies the
    # client_assertion -> CAS access-token exchange before creating boto3.
    access_token = cas_credentials.resolve_sync(default_client_context())
    print("CAS access token obtained")
    print(f"  token_type: {access_token.token_type}")
    print(f"  expires_at: {access_token.expires_at.isoformat()}")

    s3_credentials = WorkloadIdentityS3Credentials(
        cas_base_url=args.cas_base_url,
        role_name=args.role_name,
        credentials=cas_credentials,
        s3_endpoint_url=args.s3_endpoint_url,
        verify=verify,
        timeout=args.cas_timeout,
    )

    s3 = OneNexusBoto3Bridge.create_s3_client(
        s3_credentials,
        region_name=args.region,
        verify=verify,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )

    response = s3.list_buckets()
    buckets = response.get("Buckets", [])

    print("Buckets:")
    if not buckets:
        print("  <none>")
        return

    for bucket in buckets:
        print(f"  - {bucket['Name']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Exchange a CAS service-client private_key_jwt for a CAS token, "
            "assume an S3 role through CAS, and list S3 buckets with boto3."
        )
    )
    parser.add_argument("--cas-base-url", default=DEFAULT_CAS_BASE_URL)
    parser.add_argument("--s3-endpoint-url", default=DEFAULT_S3_ENDPOINT_URL)
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    parser.add_argument(
        "--private-jwk",
        type=Path,
        default=DEFAULT_PRIVATE_JWK_PATH,
        help="Path to the service-client private JWK JSON file.",
    )
    parser.add_argument("--role-name", default=DEFAULT_ROLE_NAME)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification for local self-signed minikube certificates.",
    )
    parser.add_argument(
        "--cas-timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds for CAS AssumeS3Role refresh calls.",
    )
    return parser.parse_args()


def load_private_jwk(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"private JWK file {path} must contain a JSON object")
    if "d" not in value:
        raise ValueError(
            f"private JWK file {path} does not contain private key material"
        )
    return value


if __name__ == "__main__":
    main()

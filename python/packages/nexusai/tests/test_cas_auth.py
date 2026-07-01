import base64
import json
import unittest
from datetime import UTC, datetime

from nexusai.auth import decode_jwt_payload, token_profile
from nexusai.cas import access_token_from_string
from nexusai.client import OneNexusClient


def fake_jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}
    parts = []
    for item in (header, payload):
        raw = json.dumps(item, separators=(",", ":")).encode("utf-8")
        parts.append(base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="))
    return f"{parts[0]}.{parts[1]}.signature"


class CasAuthTest(unittest.TestCase):
    def test_decode_jwt_payload_without_verifying_signature(self):
        token = fake_jwt(
            {
                "iss": "https://cas.test",
                "sub": "user-1",
                "tid": "tenant-1",
                "email": "user@example.com",
                "exp": 1_893_456_000,
            }
        )

        self.assertEqual(decode_jwt_payload(token)["tid"], "tenant-1")
        profile = token_profile(token)
        self.assertEqual(profile["tenant_id"], "tenant-1")
        self.assertEqual(profile["email"], "user@example.com")
        self.assertEqual(profile["token_type"], "jwt")

    def test_access_token_uses_jwt_expiration(self):
        token = fake_jwt({"exp": 1_893_456_000})

        access_token = access_token_from_string(token)

        self.assertEqual(access_token.access_token, token)
        self.assertEqual(access_token.expires_at, datetime.fromtimestamp(1_893_456_000, UTC))

    def test_client_accepts_access_token_alias(self):
        client = OneNexusClient(access_token="opaque-token")

        self.assertEqual(client.access_token, "opaque-token")
        self.assertEqual(client.personal_token, "opaque-token")


if __name__ == "__main__":
    unittest.main()

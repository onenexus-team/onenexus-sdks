import getpass
import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CAS_BASE_URL, PLATFORM_BASE_URL

TOKEN_ENV_NAME = "NEXUSAI_PERSONAL_TOKEN"
ACCESS_TOKEN_ENV_NAME = "NEXUSAI_ACCESS_TOKEN"
URL_ENV_NAME = "NEXUSAI_API_URL"
CAS_URL_ENV_NAME = "NEXUSAI_CAS_URL"
CONFIG_DIR = Path.home() / ".nexusai"
TOKEN_FILE = CONFIG_DIR / "personal_token"
API_URL_FILE = CONFIG_DIR / "api_url"
CAS_URL_FILE = CONFIG_DIR / "cas_url"


def load_token(explicit_token: str | None = None) -> str | None:
    if explicit_token:
        return explicit_token
    if os.getenv(ACCESS_TOKEN_ENV_NAME):
        return os.getenv(ACCESS_TOKEN_ENV_NAME)
    if os.getenv(TOKEN_ENV_NAME):
        return os.getenv(TOKEN_ENV_NAME)
    if TOKEN_FILE.is_file():
        token = TOKEN_FILE.read_text().strip()
        if token:
            return token
    return None


def save_token(token: str) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token.strip())
    TOKEN_FILE.chmod(0o600)


def load_api_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    if os.getenv(URL_ENV_NAME):
        return os.getenv(URL_ENV_NAME, "").strip()
    if API_URL_FILE.is_file():
        url = API_URL_FILE.read_text().strip()
        if url:
            return url
    return PLATFORM_BASE_URL


def load_cas_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    if os.getenv(CAS_URL_ENV_NAME):
        return os.getenv(CAS_URL_ENV_NAME, "").strip()
    if CAS_URL_FILE.is_file():
        url = CAS_URL_FILE.read_text().strip()
        if url:
            return url
    return CAS_BASE_URL


def save_api_url(url: str) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    API_URL_FILE.write_text(url.strip())
    API_URL_FILE.chmod(0o600)


def save_cas_url(url: str) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    CAS_URL_FILE.write_text(url.strip())
    CAS_URL_FILE.chmod(0o600)


def delete_token() -> bool:
    deleted = False
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        deleted = True
    if API_URL_FILE.exists():
        API_URL_FILE.unlink()
        deleted = True
    if CAS_URL_FILE.exists():
        CAS_URL_FILE.unlink()
        deleted = True
    return deleted


def save_login(token: str, api_url: str, cas_url: str | None = None) -> None:
    save_token(token)
    save_api_url(api_url)
    if cas_url:
        save_cas_url(cas_url)


def prompt_token() -> str:
    token = getpass.getpass("CAS access token: ").strip()
    if not token:
        raise ValueError("access token is required")
    return token


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(f"{payload}{padding}".encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def token_expires_at(token: str) -> datetime | None:
    payload = decode_jwt_payload(token)
    if not payload:
        return None
    exp = payload.get("exp")
    if isinstance(exp, int | float):
        return datetime.fromtimestamp(exp, UTC)
    return None


def token_profile(token: str) -> dict[str, Any]:
    payload = decode_jwt_payload(token) or {}
    expires_at = token_expires_at(token)
    return {
        "token_type": "jwt" if payload else "opaque",
        "issuer": payload.get("iss"),
        "subject": payload.get("sub"),
        "tenant_id": payload.get("tid"),
        "email": payload.get("email"),
        "preferred_username": payload.get("preferred_username"),
        "client_id": payload.get("client_id"),
        "scopes": payload.get("scope"),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "is_expired": expires_at <= datetime.now(UTC) if expires_at else None,
    }

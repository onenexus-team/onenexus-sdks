import getpass
import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CAS_BASE_URL, PLATFORM_BASE_URL

TOKEN_ENV_NAME = "NEXUSAI_TOKEN"
URL_ENV_NAME = "NEXUSAI_API_URL"
CAS_URL_ENV_NAME = "NEXUSAI_CAS_URL"
LEGACY_TOKEN_ENV_NAME = "ONENEXUS_TOKEN"
LEGACY_URL_ENV_NAME = "ONENEXUS_API_URL"
LEGACY_CAS_URL_ENV_NAME = "ONENEXUS_CAS_URL"
CONFIG_DIR = Path.home() / ".nexusai"
LEGACY_CONFIG_DIR = Path.home() / ".onenexus"
TOKEN_FILE = CONFIG_DIR / "token"
API_URL_FILE = CONFIG_DIR / "api_url"
CAS_URL_FILE = CONFIG_DIR / "cas_url"
LEGACY_TOKEN_FILE = LEGACY_CONFIG_DIR / "token"
LEGACY_API_URL_FILE = LEGACY_CONFIG_DIR / "api_url"
LEGACY_CAS_URL_FILE = LEGACY_CONFIG_DIR / "cas_url"


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _first_file(*paths: Path) -> str | None:
    for path in paths:
        if path.is_file():
            value = path.read_text().strip()
            if value:
                return value
    return None


def load_token(explicit_token: str | None = None) -> str | None:
    if explicit_token:
        return explicit_token
    return _first_env(TOKEN_ENV_NAME, LEGACY_TOKEN_ENV_NAME) or _first_file(
        TOKEN_FILE,
        LEGACY_TOKEN_FILE,
    )


def save_token(token: str) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token.strip())
    TOKEN_FILE.chmod(0o600)


def load_api_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    return (
        _first_env(URL_ENV_NAME, LEGACY_URL_ENV_NAME)
        or _first_file(API_URL_FILE, LEGACY_API_URL_FILE)
        or PLATFORM_BASE_URL
    )


def load_cas_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    return (
        _first_env(CAS_URL_ENV_NAME, LEGACY_CAS_URL_ENV_NAME)
        or _first_file(CAS_URL_FILE, LEGACY_CAS_URL_FILE)
        or CAS_BASE_URL
    )


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
    for path in (
        TOKEN_FILE,
        API_URL_FILE,
        CAS_URL_FILE,
        LEGACY_TOKEN_FILE,
        LEGACY_API_URL_FILE,
        LEGACY_CAS_URL_FILE,
    ):
        if path.exists():
            path.unlink()
            deleted = True
    return deleted


def save_login(token: str, api_url: str, cas_url: str | None = None) -> None:
    save_token(token)
    save_api_url(api_url)
    if cas_url:
        save_cas_url(cas_url)


def prompt_token() -> str:
    token = getpass.getpass("Token: ").strip()
    if not token:
        raise ValueError("token is required")
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

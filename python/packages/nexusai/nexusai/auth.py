import getpass
import base64
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from onenexus_sdk_core import PrivateKeyJwtCredentials

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
CREDENTIAL_LOGIN_FILE = CONFIG_DIR / "credential_login.json"
LEGACY_TOKEN_FILE = LEGACY_CONFIG_DIR / "token"
LEGACY_API_URL_FILE = LEGACY_CONFIG_DIR / "api_url"
LEGACY_CAS_URL_FILE = LEGACY_CONFIG_DIR / "cas_url"


@dataclass(frozen=True, slots=True)
class CredentialLogin:
    client_id: str
    key_id: str
    credential_file: str


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
    CREDENTIAL_LOGIN_FILE.unlink(missing_ok=True)


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
        CREDENTIAL_LOGIN_FILE,
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


def save_credential_login(
    *,
    client_id: str,
    key_id: str,
    credential_file: str,
    api_url: str,
    cas_url: str,
) -> CredentialLogin:
    private_key_path = _private_key_path(credential_file)
    login = CredentialLogin(
        client_id=client_id.strip(),
        key_id=key_id.strip(),
        credential_file=str(private_key_path),
    )
    if not login.client_id or not login.key_id:
        raise ValueError("client ID and key ID are required")

    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    CREDENTIAL_LOGIN_FILE.write_text(json.dumps(asdict(login), indent=2) + "\n")
    CREDENTIAL_LOGIN_FILE.chmod(0o600)
    TOKEN_FILE.unlink(missing_ok=True)
    LEGACY_TOKEN_FILE.unlink(missing_ok=True)
    save_api_url(api_url)
    save_cas_url(cas_url)
    return login


def load_credential_login() -> CredentialLogin | None:
    if not CREDENTIAL_LOGIN_FILE.is_file():
        return None
    try:
        value = json.loads(CREDENTIAL_LOGIN_FILE.read_text())
        return CredentialLogin(
            client_id=str(value["client_id"]),
            key_id=str(value["key_id"]),
            credential_file=str(value["credential_file"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("saved NexusAI credential login is invalid") from error


def create_private_key_jwt_credentials(
    login: CredentialLogin,
    *,
    cas_url: str,
) -> PrivateKeyJwtCredentials:
    private_key_path = _private_key_path(login.credential_file)
    return PrivateKeyJwtCredentials(
        issuer=cas_url,
        client_id=login.client_id,
        signing_key=private_key_path.read_text(),
        signing_key_id=login.key_id,
    )


def _private_key_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"credential file does not exist: {path}")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise ValueError(
            "credential file must only be readable by its owner; run chmod 600"
        )
    return path


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
        "claims_verified": False,
        "claims_notice": "JWT claims are decoded locally and are not authorization proof.",
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

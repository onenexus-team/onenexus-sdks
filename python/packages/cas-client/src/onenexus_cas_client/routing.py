"""Safe endpoint selection for CAS operations that follow token residency."""

from __future__ import annotations

import base64
import binascii
import json
import re
from urllib.parse import urlsplit, urlunsplit

_REGION_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")


def resolve_assume_s3_role_base_url(global_base_url: str, access_token: str) -> str:
    """Route to a trusted token issuer from the configured global ``auth.<domain>`` URL."""
    global_origin = _origin(global_base_url.rstrip("/"))
    if global_origin is None or not global_origin[1].startswith("auth."):
        raise ValueError("CAS base URL must be the global auth.<domain> endpoint.")

    global_scheme, global_host, global_port, canonical_global = global_origin
    root_domain = global_host.removeprefix("auth.")
    if not root_domain:
        raise ValueError("CAS base URL must be the global auth.<domain> endpoint.")

    claims = _jwt_claims(access_token)
    if claims is None:
        return canonical_global

    issuer = claims.get("iss")
    issuer_origin = _origin(issuer) if isinstance(issuer, str) else None
    if issuer_origin is None:
        raise ValueError("CAS access token contains an invalid issuer.")

    issuer_scheme, issuer_host, issuer_port, canonical_issuer = issuer_origin
    if (
        issuer_scheme == global_scheme
        and issuer_host == global_host
        and issuer_port == global_port
    ):
        return canonical_issuer

    if issuer_host.startswith("auth."):
        issuer_domain = issuer_host.removeprefix("auth.")
        parent_suffix = f".{issuer_domain}"
        possible_configured_region = root_domain.removesuffix(parent_suffix)
        if (
            root_domain.endswith(parent_suffix)
            and _REGION_LABEL.fullmatch(possible_configured_region) is not None
        ):
            raise ValueError("CAS base URL must be the global auth.<domain> endpoint.")

    regional_suffix = f".{root_domain}"
    region = issuer_host.removeprefix("auth.").removesuffix(regional_suffix)
    if (
        issuer_scheme != global_scheme
        or issuer_port != global_port
        or not issuer_host.startswith("auth.")
        or not issuer_host.endswith(regional_suffix)
        or _REGION_LABEL.fullmatch(region) is None
    ):
        raise ValueError("CAS access token issuer is not trusted for regional routing.")
    return canonical_issuer


def _jwt_claims(access_token: str) -> dict[str, object] | None:
    parts = access_token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    return claims if isinstance(claims, dict) else None


def _origin(value: str) -> tuple[str, str, int | None, str] | None:
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    default_port = 443 if parsed.scheme == "https" else 80
    port = None if port == default_port else port
    host = parsed.hostname.lower()
    authority = f"[{host}]" if ":" in host else host
    if port is not None:
        authority = f"{authority}:{port}"
    return parsed.scheme, host, port, urlunsplit((parsed.scheme, authority, "", "", ""))


__all__ = ["resolve_assume_s3_role_base_url"]

"""Credential primitives and concrete credential sources."""

from __future__ import annotations

from ._oidc import ServerMetadata
from .errors import AuthenticationError, StaleCredentialsError
from .model import (
    DEFAULT_REFRESH_LEEWAY,
    AccessToken,
    ClientContext,
    Clock,
    Credentials,
    SystemClock,
    default_client_context,
)
from .private_key_jwt import PrivateKeyJwtCredentials
from .token_grant import TokenGrantCredentials
from .workload_identity_file import (
    DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH,
    WORKLOAD_IDENTITY_GRANT_TYPE,
    WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE,
    WorkloadIdentityFileCredentials,
)

__all__ = [
    "DEFAULT_REFRESH_LEEWAY",
    "DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH",
    "WORKLOAD_IDENTITY_GRANT_TYPE",
    "WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE",
    "AccessToken",
    "AuthenticationError",
    "ClientContext",
    "Clock",
    "Credentials",
    "PrivateKeyJwtCredentials",
    "ServerMetadata",
    "StaleCredentialsError",
    "SystemClock",
    "TokenGrantCredentials",
    "WorkloadIdentityFileCredentials",
    "default_client_context",
]

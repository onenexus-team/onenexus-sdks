"""``onenexus-sdk-core`` — credential primitives and async HTTP transport.

The credential object system is documented in the repository ``README.md``. This
package is the Python counterpart of ``@onenexus/sdk-core``: the same
language-agnostic credential design, expressed with ``typing.Protocol``
interfaces, ``asyncio``, and ``httpx``.
"""

from __future__ import annotations

from .client import ClientBase
from .credentials import (
    DEFAULT_REFRESH_LEEWAY,
    DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH,
    WORKLOAD_IDENTITY_GRANT_TYPE,
    WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE,
    AccessToken,
    AuthenticationError,
    ClientContext,
    Clock,
    Credentials,
    PrivateKeyJwtCredentials,
    ServerMetadata,
    StaleCredentialsError,
    SystemClock,
    TokenGrantCredentials,
    WorkloadIdentityFileCredentials,
    default_client_context,
)
from .http import (
    RETRYABLE_STATUS,
    AlreadyExistsError,
    FailedPreconditionError,
    ForbiddenError,
    InternalError,
    InvalidArgumentError,
    NotFoundError,
    PlatformError,
    ResourceExhaustedError,
    RetryConfig,
    Transport,
    UnauthenticatedError,
    UnavailableError,
    parse_platform_error,
)
from .kiota import OneNexusAccessTokenProvider, create_kiota_request_adapter

__all__ = [
    "DEFAULT_REFRESH_LEEWAY",
    "DEFAULT_WORKLOAD_IDENTITY_TOKEN_PATH",
    "WORKLOAD_IDENTITY_GRANT_TYPE",
    "WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE",
    "RETRYABLE_STATUS",
    "AccessToken",
    "AlreadyExistsError",
    "AuthenticationError",
    "ClientBase",
    "ClientContext",
    "Clock",
    "Credentials",
    "FailedPreconditionError",
    "ForbiddenError",
    "InternalError",
    "InvalidArgumentError",
    "NotFoundError",
    "OneNexusAccessTokenProvider",
    "PlatformError",
    "PrivateKeyJwtCredentials",
    "ResourceExhaustedError",
    "RetryConfig",
    "ServerMetadata",
    "StaleCredentialsError",
    "SystemClock",
    "TokenGrantCredentials",
    "Transport",
    "UnauthenticatedError",
    "UnavailableError",
    "WorkloadIdentityFileCredentials",
    "create_kiota_request_adapter",
    "default_client_context",
    "parse_platform_error",
]

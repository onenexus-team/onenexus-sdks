"""boto3 ⇄ OneNexus credential bridge.

``WorkloadIdentityS3Credentials`` adapts any OneNexus :class:`Credentials`
implementation with ``resolve_sync()`` into botocore ``RefreshableCredentials``.
On each refresh it resolves a CAS access token,
calls ``AssumeS3Role``, and returns the temporary S3 credentials together with
the STS expiry, so botocore refreshes them automatically before they lapse.
"""

from __future__ import annotations

import datetime
from typing import Any

import boto3
import botocore.session
import httpx
from botocore.credentials import RefreshableCredentials
from onenexus_cas_client import AssumeS3RoleResponse
from onenexus_sdk_core import (
    ClientContext,
    Credentials,
    default_client_context,
    parse_platform_error,
)

#: botocore refresh method label, surfaced in botocore debug logs.
_REFRESH_METHOD = "onenexus-workload-identity"

#: Default S3 region. RGW ignores it, but botocore's SigV4 signer requires one.
_DEFAULT_REGION = "us-east-1"


def _to_botocore_metadata(response: AssumeS3RoleResponse) -> dict[str, str]:
    """Map a CAS ``AssumeS3Role`` response to botocore credential metadata.

    Raises:
        RuntimeError: if CAS returned an incomplete credential set.
    """
    if (
        response.access_key_id is None
        or response.secret_access_key is None
        or response.session_token is None
        or response.expiration is None
    ):
        raise RuntimeError("CAS AssumeS3Role returned an incomplete credential set.")

    return {
        "access_key": response.access_key_id,
        "secret_key": response.secret_access_key,
        "token": response.session_token,
        # botocore parses ISO 8601; the value is timezone-aware from CAS.
        "expiry_time": response.expiration.isoformat(),
    }


class WorkloadIdentityS3Credentials:
    """Auto-refreshing boto3 credentials sourced from CAS ``AssumeS3Role``.

    Example:
        >>> from onenexus_sdk_core import WorkloadIdentityFileCredentials
        >>> creds = WorkloadIdentityFileCredentials(issuer="https://cas.example")
        >>> s3_creds = WorkloadIdentityS3Credentials(
        ...     cas_base_url="https://cas.example",
        ...     role_name="S3ObjectFullAccess",
        ...     credentials=creds,
        ...     s3_endpoint_url="https://s3.example",
        ... )
        >>> s3 = OneNexusBoto3Bridge.create_s3_client(s3_creds)
        >>> s3.list_buckets()

    The instance owns no background event loop. It uses synchronous HTTP calls
    for the CAS ``AssumeS3Role`` refresh path because botocore refresh callbacks
    are synchronous.
    """

    def __init__(
        self,
        *,
        cas_base_url: str,
        role_name: str,
        credentials: Credentials,
        s3_endpoint_url: str | None = None,
        s3_region_name: str = _DEFAULT_REGION,
        context: ClientContext | None = None,
        verify: bool | str = True,
        timeout: httpx.Timeout | float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._cas_base_url = cas_base_url
        self._role_name = role_name
        self._credentials = credentials
        self._s3_endpoint_url = s3_endpoint_url
        self._s3_region_name = s3_region_name
        self._context = context or default_client_context()
        self._verify = verify
        self._timeout = timeout
        self._transport = transport
        # Seed with an initial assume so the first client call has live creds;
        # botocore then calls _refresh again on its own schedule before expiry.
        self._refreshable = RefreshableCredentials.create_from_metadata(
            metadata=self._refresh(),
            refresh_using=self._refresh,
            method=_REFRESH_METHOD,
        )

    @property
    def refreshable_credentials(self) -> RefreshableCredentials:
        """The underlying botocore ``RefreshableCredentials``."""
        return self._refreshable

    def client(
        self,
        *,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Build a boto3 S3 client wired to the auto-refreshing credentials."""
        endpoint_url = endpoint_url or self._s3_endpoint_url
        if endpoint_url is None:
            raise ValueError("endpoint_url is required (pass it to the credentials or client()).")
        region_name = region_name or self._s3_region_name
        botocore_session = botocore.session.get_session()
        # Inject our refreshable credentials as the session's credential source.
        botocore_session._credentials = self._refreshable
        session = boto3.Session(botocore_session=botocore_session, region_name=region_name)
        return session.client("s3", endpoint_url=endpoint_url, **kwargs)

    def _refresh(self) -> dict[str, str]:
        response = self._assume_sync()
        return _to_botocore_metadata(response)

    def _assume_sync(self) -> AssumeS3RoleResponse:
        token = self._credentials.resolve_sync(self._context)
        with httpx.Client(
            base_url=self._cas_base_url,
            verify=self._verify,
            timeout=self._timeout,
            transport=self._transport,
        ) as http:
            response = http.post(
                "/api/AssumeS3Role",
                json={"roleName": self._role_name},
                headers={
                    "Accept": "application/json",
                    "Authorization": f"{token.token_type} {token.access_token}",
                },
            )
        if not response.is_success:
            raise parse_platform_error(response)

        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("CAS AssumeS3Role returned a non-object response.")
        return AssumeS3RoleResponse(
            access_key_id=_optional_str(body.get("accessKeyId")),
            secret_access_key=_optional_str(body.get("secretAccessKey")),
            session_token=_optional_str(body.get("sessionToken")),
            expiration=_optional_datetime(body.get("expiration")),
        )

    def close(self) -> None:
        """Compatibility no-op; the bridge no longer owns background resources."""

    def __enter__(self) -> WorkloadIdentityS3Credentials:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class OneNexusBoto3Bridge:
    """Factory helpers for boto3 clients backed by OneNexus credentials."""

    @staticmethod
    def create_s3_client(
        credentials: WorkloadIdentityS3Credentials,
        *,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a boto3 S3 client backed by auto-refreshing OneNexus creds."""
        return credentials.client(endpoint_url=endpoint_url, region_name=region_name, **kwargs)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_datetime(value: object) -> datetime.datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


__all__ = ["OneNexusBoto3Bridge", "WorkloadIdentityS3Credentials"]

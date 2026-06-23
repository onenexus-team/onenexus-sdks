"""``onenexus-boto3`` — boto3 credential bridge for the OneNexus platform.

Wraps OneNexus workload-identity credentials as auto-refreshing boto3
credentials. A workload that holds a
:class:`onenexus_sdk_core.WorkloadIdentityFileCredentials` can hand it to
:class:`WorkloadIdentityS3Credentials` and create an S3 client via
:class:`OneNexusBoto3Bridge` whose temporary credentials are minted via CAS
``AssumeS3Role`` and refreshed automatically by botocore before they expire.
"""

from __future__ import annotations

from .credentials import OneNexusBoto3Bridge, WorkloadIdentityS3Credentials

__all__ = ["OneNexusBoto3Bridge", "WorkloadIdentityS3Credentials"]

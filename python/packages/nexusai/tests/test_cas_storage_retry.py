from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from kiota_abstractions.api_error import APIError
from onenexus_cas_client import AssumeS3RoleResponse

import nexusai._internal.cas_storage as cas_storage
from nexusai import RetryPolicy


class CasClient:
    def __init__(self, responses: list[object], close_count: list[int]) -> None:
        self._responses = responses
        self._close_count = close_count

    async def assume_s3_role(self, _request: object) -> AssumeS3RoleResponse:
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, AssumeS3RoleResponse)
        return response

    async def aclose(self) -> None:
        self._close_count[0] += 1


def credential_response() -> AssumeS3RoleResponse:
    return AssumeS3RoleResponse(
        access_key_id="access",
        secret_access_key="secret",
        session_token="session",
        expiration=datetime.now(UTC) + timedelta(hours=1),
    )


def test_runtime_credential_retries_transient_cas_error(monkeypatch) -> None:
    responses: list[object] = [
        APIError(
            message="unavailable",
            response_status_code=503,
            response_headers={"Retry-After": "0"},
        ),
        credential_response(),
    ]
    close_count = [0]
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(cas_storage.asyncio, "sleep", record_sleep)

    credential = cas_storage.create_runtime_s3_credential(
        cas_client_factory=lambda: CasClient(responses, close_count),
        role_name="S3ObjectFullAccess",
        endpoint_url="https://s3.example.test",
        bucket="bucket",
        prefix="prefix",
        retry_policy=RetryPolicy(base_delay_seconds=0),
    )

    assert credential["access_key"] == "access"
    assert credential["bucket"] == "bucket"
    assert responses == []
    assert delays == [0.0]
    assert close_count == [2]


@pytest.mark.parametrize(
    ("policy", "expected_calls"),
    [
        (RetryPolicy(max_attempts=3, base_delay_seconds=0), 1),
        (RetryPolicy(enabled=False), 1),
    ],
)
def test_runtime_credential_does_not_retry_forbidden_or_disabled_policy(
    monkeypatch,
    policy: RetryPolicy,
    expected_calls: int,
) -> None:
    responses: list[object] = [
        APIError(message="forbidden", response_status_code=403),
        credential_response(),
    ]
    close_count = [0]

    async def fail_sleep(_delay: float) -> None:
        raise AssertionError("non-retryable CAS error must not sleep")

    monkeypatch.setattr(cas_storage.asyncio, "sleep", fail_sleep)

    with pytest.raises(APIError):
        cas_storage.create_runtime_s3_credential(
            cas_client_factory=lambda: CasClient(responses, close_count),
            role_name="S3ObjectFullAccess",
            endpoint_url="https://s3.example.test",
            bucket="bucket",
            prefix="prefix",
            retry_policy=policy,
        )

    assert close_count == [expected_calls]


def test_runtime_credential_respects_disabled_retry_for_transient_error(
    monkeypatch,
) -> None:
    responses: list[object] = [
        APIError(message="unavailable", response_status_code=503),
        credential_response(),
    ]
    close_count = [0]

    async def fail_sleep(_delay: float) -> None:
        raise AssertionError("disabled retry policy must not sleep")

    monkeypatch.setattr(cas_storage.asyncio, "sleep", fail_sleep)

    with pytest.raises(APIError):
        cas_storage.create_runtime_s3_credential(
            cas_client_factory=lambda: CasClient(responses, close_count),
            role_name="S3ObjectFullAccess",
            endpoint_url="https://s3.example.test",
            bucket="bucket",
            prefix="prefix",
            retry_policy=RetryPolicy(enabled=False),
        )

    assert close_count == [1]

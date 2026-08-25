from __future__ import annotations

import io
import json
from urllib.error import HTTPError, URLError

import pytest

import nexusai._internal.http as http_module
from nexusai import RetryPolicy
from nexusai.errors import OneNexusAPIError, OneNexusError
from nexusai._internal.http import APIClient


class Response:
    status = 200

    def __init__(
        self,
        payload: object,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._payload = json.dumps(payload).encode()
        self.headers = headers or {}

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def http_error(
    status: int,
    *,
    retry_after: str | None = None,
    idempotency_status: str | None = None,
) -> HTTPError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    if idempotency_status is not None:
        headers["X-Idempotency-Status"] = idempotency_status
    return HTTPError(
        "https://api.example.test",
        status,
        "temporary failure",
        headers,
        io.BytesIO(b'{"code":"TEMPORARY","message":"retry"}'),
    )


def client(*, max_attempts: int = 3) -> APIClient:
    return APIClient(
        token="token",
        base_url="https://api.example.test",
        retry_policy=RetryPolicy(
            max_attempts=max_attempts,
            max_elapsed_seconds=30,
            base_delay_seconds=0,
            max_delay_seconds=10,
        ),
    )


def test_read_operation_retries_transient_http_error(monkeypatch) -> None:
    attempts = [http_error(503), Response({"items": [], "total_pages": 0})]

    def send(*_args, **_kwargs):
        response = attempts.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    monkeypatch.setattr(http_module, "urlopen", send)
    monkeypatch.setattr(http_module.time, "sleep", lambda _delay: None)

    assert client().post_list("/v1/DataHub/ListDatasets", {}) == []
    assert attempts == []


def test_list_operation_omits_unspecified_optional_fields(monkeypatch) -> None:
    requests = []

    def send(request, **_kwargs):
        requests.append(request)
        return Response({"items": [], "total_pages": 0})

    monkeypatch.setattr(http_module, "urlopen", send)

    assert client().post_list(
        "/v1/DataHub/ListDatasets",
        {"page": None, "limit": 1, "name": None},
    ) == []
    assert json.loads(requests[0].data) == {"limit": 1}


def test_mutation_gets_stable_generated_idempotency_key_for_retry(
    monkeypatch,
) -> None:
    responses = [http_error(503), Response({"data": {"id": "dataset-1"}})]
    requests = []

    def send(request, **_kwargs):
        requests.append(request)
        response = responses.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    monkeypatch.setattr(http_module, "urlopen", send)
    monkeypatch.setattr(http_module.time, "sleep", lambda _delay: None)

    result = client().post("/v1/DataHub/CreateDataset", {"name": "dataset"})

    assert result == {"id": "dataset-1"}
    assert len(requests) == 2
    first_key = requests[0].get_header("Idempotency-key")
    assert first_key
    assert requests[1].get_header("Idempotency-key") == first_key


def test_mutation_with_stable_idempotency_key_can_retry(monkeypatch) -> None:
    responses = [http_error(503), Response({"data": {"id": "dataset-1"}})]
    requests = []

    def send(request, **_kwargs):
        requests.append(request)
        response = responses.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    monkeypatch.setattr(http_module, "urlopen", send)
    monkeypatch.setattr(http_module.time, "sleep", lambda _delay: None)

    result = client().post(
        "/v1/DataHub/StartDatasetUpload",
        {"dataset_id": "dataset-1", "idempotency_key": "stable-key"},
    )

    assert result == {"id": "dataset-1"}
    assert len(requests) == 2
    assert requests[0].data == requests[1].data
    assert requests[0].get_header("X-request-id") is None
    assert requests[0].get_header("Idempotency-key") == "stable-key"


def test_idempotency_in_progress_is_the_only_retryable_conflict(monkeypatch) -> None:
    responses = [
        http_error(
            409,
            retry_after="0",
            idempotency_status="idempotency_in_progress",
        ),
        Response({"data": {"id": "dataset-1"}}),
    ]
    calls = 0

    def send(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        response = responses.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    monkeypatch.setattr(http_module, "urlopen", send)
    monkeypatch.setattr(http_module.time, "sleep", lambda _delay: None)

    result = client().post("/v1/DataHub/CreateDataset", {"name": "dataset"})

    assert result == {"id": "dataset-1"}
    assert calls == 2


def test_normal_conflict_is_not_retried(monkeypatch) -> None:
    calls = 0

    def fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise http_error(409)

    monkeypatch.setattr(http_module, "urlopen", fail)

    with pytest.raises(OneNexusAPIError):
        client().post("/v1/DataHub/CreateDataset", {"name": "dataset"})

    assert calls == 1


def test_workload_mutation_without_domain_idempotency_is_not_retried(
    monkeypatch,
) -> None:
    calls = 0

    def fail(request, **_kwargs):
        nonlocal calls
        calls += 1
        assert request.get_header("Idempotency-key") is None
        raise http_error(503)

    monkeypatch.setattr(http_module, "urlopen", fail)

    with pytest.raises(OneNexusAPIError):
        client().post(
            "/workload/v1/Training/FinalizeCheckpointUpload",
            {"checkpoint_id": "checkpoint-1"},
        )

    assert calls == 1


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/v1/DataHub/CreateDataset", {"name": "dataset"}),
        (
            "/v1/DataHub/FinalizeDatasetUpload",
            {"dataset_id": "dataset-1"},
        ),
    ],
)
def test_lost_response_retry_does_not_repeat_backend_mutation(
    monkeypatch,
    path: str,
    body: dict[str, str],
) -> None:
    responses_by_key: dict[str, object] = {}
    mutation_count = 0

    def send(request, **_kwargs):
        nonlocal mutation_count
        key = request.get_header("Idempotency-key")
        assert key
        if key not in responses_by_key:
            mutation_count += 1
            responses_by_key[key] = {
                "data": {"resource_id": "dataset-1", "status": "READY"}
            }
            raise URLError("response lost after backend commit")
        return Response(responses_by_key[key])

    monkeypatch.setattr(http_module, "urlopen", send)
    monkeypatch.setattr(http_module.time, "sleep", lambda _delay: None)

    result = client().post(path, body)

    assert result["resource_id"] == "dataset-1"
    assert mutation_count == 1
    assert len(responses_by_key) == 1


def test_retry_exhaustion_has_bounded_attempt_count(monkeypatch) -> None:
    calls = 0

    def fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise URLError("network unavailable")

    monkeypatch.setattr(http_module, "urlopen", fail)
    monkeypatch.setattr(http_module.time, "sleep", lambda _delay: None)

    with pytest.raises(OneNexusError, match="Could not connect"):
        client(max_attempts=3).post("/v1/DataHub/GetDataset", {"dataset_id": "d"})

    assert calls == 3


def test_retry_after_controls_delay(monkeypatch) -> None:
    responses = [http_error(429, retry_after="2"), Response({"data": {}})]
    delays: list[float] = []

    def send(*_args, **_kwargs):
        response = responses.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    monkeypatch.setattr(http_module, "urlopen", send)
    monkeypatch.setattr(http_module.time, "sleep", delays.append)

    client().post("/v1/DataHub/GetDataset", {"dataset_id": "d"})

    assert delays == [2.0]


def test_requests_include_sdk_version_but_not_caller_request_id(monkeypatch) -> None:
    requests = []

    def send(request, **_kwargs):
        requests.append(request)
        return Response({"data": {}})

    monkeypatch.setattr(http_module, "urlopen", send)

    client().post("/v1/DataHub/GetDataset", {"dataset_id": "d"})

    assert requests[0].get_header("User-agent").startswith("nexusai/")
    assert requests[0].get_header("X-request-id") is None


def test_response_and_error_request_ids_prefer_server_headers(monkeypatch) -> None:
    responses = [
        Response(
            {"items": [], "total_pages": 0},
            headers={"X-Request-ID": "server-request-1"},
        ),
        HTTPError(
            "https://api.example.test",
            404,
            "not found",
            {"X-Request-ID": "server-request-2"},
            io.BytesIO(
                b'{"type":"https://api.onenexus.vn/problems/resource-not-found",'
                b'"title":"Resource not found","status":404,"detail":"missing",'
                b'"instance":"urn:onenexus:request:server-request-2"}'
            ),
        ),
    ]

    def send(*_args, **_kwargs):
        response = responses.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    monkeypatch.setattr(http_module, "urlopen", send)
    api = client()

    page = api.post_page("/v1/DataHub/ListDatasets", type("Item", (), {}))
    assert page.request_id == "server-request-1"
    with pytest.raises(OneNexusAPIError) as caught:
        api.post("/v1/DataHub/GetDataset", {"dataset_id": "missing"})
    assert caught.value.request_id == "server-request-2"
    assert caught.value.problem_type.endswith("/resource-not-found")
    assert caught.value.title == "Resource not found"
    assert caught.value.detail == "missing"

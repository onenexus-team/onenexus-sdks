from pathlib import Path

import pytest

from nexusai import RetryPolicy
from nexusai._internal import data_hub_transfer
from nexusai._internal.data_hub_transfer import DataHubTransferClient
from nexusai._internal.storage import StorageTransferFile
from nexusai.errors import OneNexusAPIError, OneNexusError


class AssumeS3RoleResponse:
    access_key_id = "runtime-access"
    secret_access_key = "runtime-secret"
    session_token = "runtime-session"
    expiration = None


class FakeCasClient:
    def __init__(self):
        self.assume_calls = []
        self.closed = False

    async def assume_s3_role(self, request):
        self.assume_calls.append(request.role_name)
        return AssumeS3RoleResponse()

    async def aclose(self):
        self.closed = True


class UploadedFile:
    def __init__(self, object_key, size_bytes):
        self.object_key = object_key
        self.size_bytes = size_bytes


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.retry_policy = RetryPolicy(enabled=False)
        self.post_dict = self.post
        self.post_list = self.post

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return {"ok": True}

    def post(self, path, body=None):
        self.calls.append(("POST", path, body))
        if path == "/v1/DataHub/CreateDataset":
            return {"id": "dataset-1", "name": body["name"]}
        if path == "/v1/DataHub/GetDataset":
            return {"id": body["dataset_id"], "name": "dataset", "status": "FINALIZED"}
        if path == "/v1/DataHub/StartDatasetUpload":
            return {"id": "upload-session-1"}
        if path == "/protected/v1/DataHub/GetDatasetTransferTarget":
            return {"bucket": "data-bucket", "prefix": "dataset-1"}
        if path == "/v1/DataHub/FinalizeDatasetUpload":
            return {"id": "upload-session-1", "status": "FINALIZED"}
        return {"ok": True}


def test_data_hub_transport_upload_instruction_uses_pascal_case_endpoint():
    api = FakeAPI()
    client = DataHubTransferClient(api)

    client.upload_dataset_instruction("dataset-1")

    assert api.calls == [
        (
            "POST",
            "/v1/DataHub/GetUploadDatasetInstruction",
            {"dataset_id": "dataset-1"},
        )
    ]


def test_dataset_upload_uses_runtime_cas_credential(monkeypatch):
    api = FakeAPI()
    cas = FakeCasClient()
    client = DataHubTransferClient(
        api,
        cas_client_factory=lambda: cas,
        s3_endpoint_url="https://s3.test",
        s3_role_name="S3ObjectFullAccess",
    )
    upload_calls = []

    def fake_upload_path(source_path, credential):
        upload_calls.append((source_path, credential))
        return [UploadedFile("dataset-1/train.jsonl", 10)]

    monkeypatch.setattr(data_hub_transfer, "upload_path", fake_upload_path)

    result = client.upload_dataset(name="dataset", source_path="/tmp/data")

    assert result.resource == {
        "id": "dataset-1",
        "name": "dataset",
        "status": "FINALIZED",
    }
    assert upload_calls == [
        (
            "/tmp/data",
            {
                "endpoint_url": "https://s3.test",
                "bucket": "data-bucket",
                "prefix": "dataset-1",
                "access_key": "runtime-access",
                "secret_key": "runtime-secret",
                "session_token": "runtime-session",
                "expires_at": None,
            },
        )
    ]
    assert cas.assume_calls == ["S3ObjectFullAccess"]
    assert cas.closed is True
    assert api.calls == [
        (
            "POST",
            "/v1/DataHub/CreateDataset",
            {"name": "dataset", "extras_data": None},
        ),
        (
            "POST",
            "/v1/DataHub/StartDatasetUpload",
            {
                "dataset_id": "dataset-1",
                "idempotency_key": None,
                "declared_manifest": None,
                "reserved_quota_bytes": 0,
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/protected/v1/DataHub/GetDatasetTransferTarget",
            {"dataset_id": "dataset-1"},
        ),
        (
            "POST",
            "/v1/DataHub/FinalizeDatasetUpload",
            {
                "dataset_id": "dataset-1",
                "manifest": {"files": [{"path": "train.jsonl", "size": 10}]},
                "file_count": 1,
                "total_size_bytes": 10,
            },
        ),
        (
            "POST",
            "/v1/DataHub/GetDataset",
            {"dataset_id": "dataset-1"},
        ),
    ]


class SequencedDatasetAPI(FakeAPI):
    def __init__(self, *dataset_responses):
        super().__init__()
        self._dataset_responses = list(dataset_responses)

    def post(self, path, body=None):
        if path == "/v1/DataHub/GetDataset":
            self.calls.append(("POST", path, body))
            response = self._dataset_responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return {"id": body["dataset_id"], "name": "dataset", "status": response}
        return super().post(path, body)


def _download_client(api):
    return DataHubTransferClient(
        api,
        cas_client_factory=FakeCasClient,
        s3_endpoint_url="https://s3.test",
    )


def _fake_download_prefix(downloads):
    def fake_download_prefix(destination_path, credential):
        downloads.append(destination_path)
        local_path = Path(destination_path) / "nested" / "train.jsonl"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text("{}\n")
        return [
            StorageTransferFile(
                local_path=str(local_path),
                object_key="dataset-1/nested/train.jsonl",
                relative_path="nested/train.jsonl",
                size_bytes=3,
            )
        ]

    return fake_download_prefix


def test_dataset_download_publishes_files_after_status_recheck(monkeypatch, tmp_path):
    api = SequencedDatasetAPI("READY", "READY")
    downloads = []
    monkeypatch.setattr(
        data_hub_transfer, "download_prefix", _fake_download_prefix(downloads)
    )

    result = _download_client(api).download_dataset("dataset-1", str(tmp_path))

    final_path = tmp_path / "nested" / "train.jsonl"
    assert final_path.read_text() == "{}\n"
    assert [file.local_path for file in result.files] == [str(final_path)]
    assert result.resource["status"] == "READY"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["nested"]
    assert [call[1] for call in api.calls] == [
        "/v1/DataHub/GetDataset",
        "/protected/v1/DataHub/GetDatasetTransferTarget",
        "/v1/DataHub/GetDataset",
    ]


@pytest.mark.parametrize("status", ["DELETING", "DELETED", "UPLOADING", None])
def test_dataset_download_refuses_undownloadable_status(monkeypatch, tmp_path, status):
    api = SequencedDatasetAPI(status)
    downloads = []
    monkeypatch.setattr(
        data_hub_transfer, "download_prefix", _fake_download_prefix(downloads)
    )

    with pytest.raises(OneNexusError, match="cannot be downloaded"):
        _download_client(api).download_dataset("dataset-1", str(tmp_path))

    assert downloads == []
    assert [call[1] for call in api.calls] == ["/v1/DataHub/GetDataset"]


@pytest.mark.parametrize(
    "recheck",
    [
        "DELETING",
        "DELETED",
        OneNexusAPIError(404, "Not Found", "dataset not found"),
    ],
)
def test_dataset_download_during_concurrent_delete_fails_closed(
    monkeypatch, tmp_path, recheck
):
    api = SequencedDatasetAPI("FINALIZED", recheck)
    downloads = []
    monkeypatch.setattr(
        data_hub_transfer, "download_prefix", _fake_download_prefix(downloads)
    )

    with pytest.raises(OneNexusError):
        _download_client(api).download_dataset("dataset-1", str(tmp_path))

    assert len(downloads) == 1
    assert list(tmp_path.iterdir()) == []


def test_dataset_download_storage_failure_leaves_no_partial_files(
    monkeypatch, tmp_path
):
    api = SequencedDatasetAPI("READY")

    def failing_download_prefix(destination_path, credential):
        partial = Path(destination_path) / "train.jsonl"
        partial.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text("partial")
        raise OSError("NoSuchKey")

    monkeypatch.setattr(data_hub_transfer, "download_prefix", failing_download_prefix)

    with pytest.raises(OSError, match="NoSuchKey"):
        _download_client(api).download_dataset("dataset-1", str(tmp_path))

    assert list(tmp_path.iterdir()) == []


def test_dataset_download_refuses_symlink_escape_from_destination(
    monkeypatch, tmp_path
):
    destination = tmp_path / "dest"
    outside = tmp_path / "outside"
    destination.mkdir()
    outside.mkdir()
    (destination / "nested").symlink_to(outside, target_is_directory=True)
    api = SequencedDatasetAPI("READY", "READY")
    monkeypatch.setattr(data_hub_transfer, "download_prefix", _fake_download_prefix([]))

    with pytest.raises(ValueError, match="Unsafe object key"):
        _download_client(api).download_dataset("dataset-1", str(destination))

    assert list(outside.iterdir()) == []

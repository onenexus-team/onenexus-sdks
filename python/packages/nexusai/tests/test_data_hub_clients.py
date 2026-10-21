from nexusai import RetryPolicy
from nexusai._internal import data_hub_transfer
from nexusai._internal.data_hub_transfer import DataHubTransferClient


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

import hashlib
import json

from nexusai import RetryPolicy
from nexusai._internal import model_registry_transfer
from nexusai._internal.model_registry_transfer import ModelRegistryTransferClient
from nexusai._internal.storage import StorageTransferFile


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
        if path == "/v1/ModelRegistry/GetModelVersion":
            return {"id": body["model_version_id"], "status": "UPLOADING"}
        if path == "/protected/v1/ModelRegistry/GetModelVersionTransferTarget":
            return {
                "bucket": "model-bucket",
                "prefix": "model-1/version-1",
            }
        if path == "/v1/ModelRegistry/StartModelVersionUpload":
            return {"id": body["model_version_id"], "status": "UPLOADING"}
        if path == "/v1/ModelRegistry/FinalizeModelVersionUpload":
            return {"id": body["model_version_id"], "status": "FINALIZED"}
        return {"ok": True}


def test_model_version_upload_finalizes_with_serving_manifest(monkeypatch, tmp_path):
    api = FakeAPI()
    cas = FakeCasClient()
    client = ModelRegistryTransferClient(
        api,
        cas_client_factory=lambda: cas,
        s3_endpoint_url="https://s3.test",
        s3_role_name="S3ObjectFullAccess",
    )
    upload_calls = []
    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"weights")
    config = tmp_path / "config.json"
    config.write_text('{"architectures":["Qwen3ForCausalLM"]}', encoding="utf-8")

    def fake_upload_path(source_path, credential):
        upload_calls.append((source_path, credential))
        return [
            StorageTransferFile(
                local_path=str(weights),
                object_key="model-1/version-1/model.safetensors",
                relative_path="model.safetensors",
                size_bytes=weights.stat().st_size,
            ),
            StorageTransferFile(
                local_path=str(config),
                object_key="model-1/version-1/config.json",
                relative_path="config.json",
                size_bytes=config.stat().st_size,
            ),
        ]

    monkeypatch.setattr(model_registry_transfer, "upload_path", fake_upload_path)

    result = client.upload_to_model_version(
        model_id="model-1",
        model_version_id="version-1",
        source_path=str(tmp_path),
    )

    assert result.resource == {"id": "version-1", "status": "FINALIZED"}
    assert upload_calls == [
        (
            str(tmp_path),
            {
                "endpoint_url": "https://s3.test",
                "bucket": "model-bucket",
                "prefix": "model-1/version-1",
                "access_key": "runtime-access",
                "secret_key": "runtime-secret",
                "session_token": "runtime-session",
                "expires_at": None,
            },
        )
    ]
    assert cas.assume_calls == ["S3ObjectFullAccess"]
    assert cas.closed is True
    assert api.calls[:3] == [
        (
            "POST",
            "/v1/ModelRegistry/GetModelVersion",
            {"model_id": "model-1", "model_version_id": "version-1"},
        ),
        (
            "POST",
            "/v1/ModelRegistry/StartModelVersionUpload",
            {"model_id": "model-1", "model_version_id": "version-1"},
        ),
        (
            "POST",
            "/protected/v1/ModelRegistry/GetModelVersionTransferTarget",
            {"model_id": "model-1", "model_version_id": "version-1"},
        ),
    ]
    finalize = api.calls[3][2]
    manifest = finalize["manifest"]
    assert finalize["file_count"] == 2
    assert manifest["schema_version"] == "onenexus.serving-manifest/v1"
    assert manifest["artifact_format"] == "safetensors"
    assert manifest["model_architecture"] == "Qwen3ForCausalLM"
    assert manifest["config_files"] == ["config.json"]
    declared_digest = manifest["manifest_digest"]
    manifest["manifest_digest"] = None
    assert (
        declared_digest
        == "sha256:"
        + hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )

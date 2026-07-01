from nexusai.rpc_model_registry import RpcModelRegistryClient


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
        self.post_dict = self.post
        self.post_list = self.post

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return {"ok": True}

    def post(self, path, body=None):
        self.calls.append(("POST", path, body))
        if path == "/v1/ModelRegistry/GetModelVersion":
            return {"id": body["model_version_id"], "status": "UPLOADING"}
        if path == "/v1/TenantWorkspace/ListTenantWorkspaces":
            return [{"model_registry_bucket": "model-bucket"}]
        if path == "/v1/ModelRegistry/StartModelVersionUpload":
            return {"id": body["model_version_id"], "status": "UPLOADING"}
        if path == "/v1/ModelRegistry/FinalizeModelVersionUpload":
            return {"id": body["model_version_id"], "status": "FINALIZED"}
        return {"ok": True}


def test_rpc_model_version_upload_finalizes(monkeypatch):
    from nexusai import rpc_model_registry as rpc_model_registry_module

    api = FakeAPI()
    cas = FakeCasClient()
    client = RpcModelRegistryClient(
        api,
        cas_client_factory=lambda: cas,
        s3_endpoint_url="https://s3.test",
        s3_role_name="S3ObjectFullAccess",
    )
    upload_calls = []

    def fake_upload_path(source_path, credential):
        upload_calls.append((source_path, credential))
        return [UploadedFile("model-1/version-1/weight.bin", 128)]

    monkeypatch.setattr(rpc_model_registry_module, "upload_path", fake_upload_path)

    result = client.upload_to_model_version(
        model_id="model-1",
        model_version_id="version-1",
        source_path="/tmp/model",
    )

    assert result.resource == {"id": "version-1", "status": "FINALIZED"}
    assert upload_calls == [
        (
            "/tmp/model",
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
    assert api.calls == [
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
            "/v1/TenantWorkspace/ListTenantWorkspaces",
            {"page": 1, "limit": 1},
        ),
        (
            "POST",
            "/v1/ModelRegistry/FinalizeModelVersionUpload",
            {
                "model_id": "model-1",
                "model_version_id": "version-1",
                "manifest": {"files": [{"path": "weight.bin", "size": 128}]},
                "file_count": 1,
                "total_size_bytes": 128,
            },
        ),
    ]

from nexusai.rpc_tenant_workspace import RpcTenantWorkspaceClient


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
        return {"ok": True}


def test_rpc_tenant_workspace_create_uses_pascal_case_endpoint():
    api = FakeAPI()
    client = RpcTenantWorkspaceClient(api)

    client.create_tenant_workspace(
        name="tenant-a",
        model_registry_bucket="models-a",
        datahub_bucket="data-a",
        checkpoint_bucket="checkpoints-a",
        tokenizer_bucket="tokenizers-a",
        tenant_gpus_quota=8,
        extras_data={"team": "ml"},
    )

    assert api.calls == [
        (
            "POST",
            "/v1/TenantWorkspace/CreateTenantWorkspace",
            {
                "name": "tenant-a",
                "model_registry_bucket": "models-a",
                "datahub_bucket": "data-a",
                "checkpoint_bucket": "checkpoints-a",
                "tokenizer_bucket": "tokenizers-a",
                "tenant_gpus_quota": 8,
                "extras_data": {"team": "ml"},
            },
        )
    ]


def test_rpc_tenant_workspace_get_and_list_paths():
    api = FakeAPI()
    client = RpcTenantWorkspaceClient(api)

    client.get_tenant_workspace("workspace-1")
    client.list_tenant_workspaces(name="tenant", limit=20)

    assert api.calls == [
        (
            "POST",
            "/v1/TenantWorkspace/GetTenantWorkspace",
            {"workspace_id": "workspace-1"},
        ),
        (
            "POST",
            "/v1/TenantWorkspace/ListTenantWorkspaces",
            {"limit": 20, "name": "tenant"},
        ),
    ]

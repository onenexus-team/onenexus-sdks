from nexusai.tenant_workspace import TenantWorkspaceClient


class FakeAPI:
    def __init__(self):
        self.calls = []

    def post_model(self, path, _model, body=None):
        self.calls.append(("POST", path, body))
        return object()

    def post_page(self, path, _model, body=None):
        self.calls.append(("POST", path, body))
        return object()


def test_tenant_workspace_create_uses_pascal_case_endpoint():
    api = FakeAPI()
    client = TenantWorkspaceClient(api)

    client.create_tenant_workspace(
        name="tenant-a",
        model_registry_bucket="models-a",
        datahub_bucket="data-a",
        checkpoint_bucket="checkpoints-a",
        tokenizer_bucket="tokenizers-a",
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
                "extras_data": {"team": "ml"},
            },
        )
    ]


def test_tenant_workspace_get_and_list_paths():
    api = FakeAPI()
    client = TenantWorkspaceClient(api)

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

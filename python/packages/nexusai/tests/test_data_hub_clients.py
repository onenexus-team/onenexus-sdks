from nexusai.data_hub import DataHubClient
from nexusai.rpc_data_hub import RpcDataHubClient


class FakeAPI:
    def __init__(self):
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return {"ok": True}

    def post(self, path, body=None):
        self.calls.append(("POST", path, body))
        return {"ok": True}


def test_rpc_data_hub_upload_instruction_uses_pascal_case_endpoint():
    api = FakeAPI()
    client = RpcDataHubClient(api)

    client.upload_dataset_instruction("dataset-1")

    assert api.calls == [
        (
            "POST",
            "/v1/DataHub/UploadDatasetInstruction",
            {"dataset_id": "dataset-1"},
        )
    ]


def test_rest_data_hub_upload_instruction_path():
    api = FakeAPI()
    client = DataHubClient(api)

    client.upload_dataset_instruction("dataset-1")

    assert api.calls == [
        ("GET", "/v1/datasets/dataset-1/upload-instruction", None),
    ]

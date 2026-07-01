from nexusai.platform_catalog import PlatformCatalogClient
from nexusai.rpc_platform_catalog import RpcPlatformCatalogClient


class FakeAPI:
    def __init__(self):
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return {"ok": True}

    def post(self, path, body=None):
        self.calls.append(("POST", path, body))
        return {"ok": True}

    def patch(self, path, body=None):
        self.calls.append(("PATCH", path, body))
        return {"ok": True}

    def delete(self, path):
        self.calls.append(("DELETE", path, None))
        return {"ok": True}


def test_rpc_platform_catalog_workload_image_paths():
    api = FakeAPI()
    client = RpcPlatformCatalogClient(api)

    client.create_workload_image(
        name="training",
        service="training",
        type="trainer",
        url="ghcr.io/onenexus-team/training:latest",
    )
    client.list_workload_images(service="training")
    client.get_latest_workload_image(service="training")
    client.get_workload_image("image-1")
    client.update_workload_image("image-1", latest=True)
    client.set_latest_workload_image("image-1")
    client.delete_workload_image("image-1")

    assert [call[1] for call in api.calls] == [
        "/v1/PlatformCatalog/CreateWorkloadImage",
        "/v1/PlatformCatalog/ListWorkloadImages",
        "/v1/PlatformCatalog/GetLatestWorkloadImage",
        "/v1/PlatformCatalog/GetWorkloadImage",
        "/v1/PlatformCatalog/UpdateWorkloadImage",
        "/v1/PlatformCatalog/SetLatestWorkloadImage",
        "/v1/PlatformCatalog/DeleteWorkloadImage",
    ]


def test_rpc_platform_catalog_flavor_paths():
    api = FakeAPI()
    client = RpcPlatformCatalogClient(api)

    client.create_flavor("1x1-mi355", 1, "24", "240Gi", 1)
    client.list_flavors(min_gpus=1)
    client.get_flavor("flavor-1")
    client.update_flavor("flavor-1", gpus=2)
    client.delete_flavor("flavor-1")

    assert [call[1] for call in api.calls] == [
        "/v1/PlatformCatalog/CreateFlavor",
        "/v1/PlatformCatalog/ListFlavors",
        "/v1/PlatformCatalog/GetFlavor",
        "/v1/PlatformCatalog/UpdateFlavor",
        "/v1/PlatformCatalog/DeleteFlavor",
    ]


def test_rpc_platform_catalog_configuration_paths():
    api = FakeAPI()
    client = RpcPlatformCatalogClient(api)

    client.create_training_configuration("pretraining")
    client.list_training_configurations(training_type="pretraining")
    client.get_training_configuration("training-config-1")
    client.update_training_configuration("training-config-1", training_type="sft")
    client.delete_training_configuration("training-config-1")
    client.create_inference_configuration("sglang")
    client.list_inference_configurations(runtime="sglang")
    client.get_inference_configuration("inference-config-1")
    client.update_inference_configuration("inference-config-1", runtime="vllm")
    client.delete_inference_configuration("inference-config-1")

    assert [call[1] for call in api.calls] == [
        "/v1/PlatformCatalog/CreateTrainingConfiguration",
        "/v1/PlatformCatalog/ListTrainingConfigurations",
        "/v1/PlatformCatalog/GetTrainingConfiguration",
        "/v1/PlatformCatalog/UpdateTrainingConfiguration",
        "/v1/PlatformCatalog/DeleteTrainingConfiguration",
        "/v1/PlatformCatalog/CreateInferenceConfiguration",
        "/v1/PlatformCatalog/ListInferenceConfigurations",
        "/v1/PlatformCatalog/GetInferenceConfiguration",
        "/v1/PlatformCatalog/UpdateInferenceConfiguration",
        "/v1/PlatformCatalog/DeleteInferenceConfiguration",
    ]


def test_rest_platform_catalog_smoke_paths():
    api = FakeAPI()
    client = PlatformCatalogClient(api)

    client.list_workload_images(service="training")
    client.get_latest_workload_image(service="training")
    client.set_latest_workload_image("image-1")
    client.list_flavors(name="1x1")
    client.list_training_configurations(training_type="pretraining")
    client.list_inference_configurations(runtime="sglang")

    assert api.calls == [
        (
            "GET",
            "/v1/platform-catalog/workload-images",
            {"service": "training"},
        ),
        (
            "GET",
            "/v1/platform-catalog/workload-images/latest",
            {"service": "training"},
        ),
        (
            "POST",
            "/v1/platform-catalog/workload-images/image-1/latest",
            None,
        ),
        ("GET", "/v1/platform-catalog/flavors", {"name": "1x1"}),
        (
            "GET",
            "/v1/platform-catalog/training-configurations",
            {"training_type": "pretraining"},
        ),
        (
            "GET",
            "/v1/platform-catalog/inference-configurations",
            {"runtime": "sglang"},
        ),
    ]

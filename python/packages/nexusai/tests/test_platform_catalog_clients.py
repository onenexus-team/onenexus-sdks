from nexusai.platform_catalog import PlatformCatalogClient


class FakeAPI:
    def __init__(self):
        self.calls = []

    def post_model(self, path, _model, body=None):
        self.calls.append(("POST", path, body))
        return object()

    def post_page(self, path, _model, body=None):
        self.calls.append(("POST", path, body))
        return object()


def test_platform_catalog_does_not_expose_admin_mutations():
    client = PlatformCatalogClient(FakeAPI())

    prohibited = {
        "create_workload_image",
        "list_workload_images",
        "create_flavor",
        "update_flavor",
        "delete_flavor",
        "create_training_configuration",
        "update_training_configuration",
        "delete_training_configuration",
        "create_inference_configuration",
        "update_inference_configuration",
        "delete_inference_configuration",
    }
    assert not any(hasattr(client, name) for name in prohibited)


def test_platform_catalog_flavor_paths():
    api = FakeAPI()
    client = PlatformCatalogClient(api)

    client.list_flavors(min_gpus=1)
    client.get_flavor("flavor-1")

    assert [call[1] for call in api.calls] == [
        "/v1/PlatformCatalog/ListFlavors",
        "/v1/PlatformCatalog/GetFlavor",
    ]


def test_platform_catalog_configuration_paths():
    api = FakeAPI()
    client = PlatformCatalogClient(api)

    client.list_training_configurations(training_type="pretraining")
    client.get_training_configuration("training-config-1")
    client.list_inference_configurations(runtime="sglang")
    client.get_inference_configuration("inference-config-1")

    assert [call[1] for call in api.calls] == [
        "/v1/PlatformCatalog/ListTrainingConfigurations",
        "/v1/PlatformCatalog/GetTrainingConfiguration",
        "/v1/PlatformCatalog/ListInferenceConfigurations",
        "/v1/PlatformCatalog/GetInferenceConfiguration",
    ]

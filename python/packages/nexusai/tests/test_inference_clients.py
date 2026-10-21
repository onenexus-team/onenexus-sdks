from nexusai.inference import InferenceClient


class FakeAPI:
    def __init__(self):
        self.calls = []

    def post_model(self, path, _model, body=None):
        self.calls.append(("POST", path, body))
        return object()

    def post_optional_model(self, path, _model, body=None):
        self.calls.append(("POST", path, body))
        return object()

    def post_page(self, path, _model, body=None):
        self.calls.append(("POST", path, body))
        return object()


def test_inference_create_instance_uses_id_based_pascal_case_endpoint():
    api = FakeAPI()
    client = InferenceClient(api)

    client.create_inference_instance(
        name="qwen3-8b",
        model_id="Qwen/Qwen3-8B",
        model_version_id="model-version-1",
        served_model_name="qwen3-8b",
        flavor="1x1-mi355",
        configuration={"runtime": "sglang"},
    )

    assert api.calls == [
        (
            "POST",
            "/v1/Inference/CreateInferenceInstance",
            {
                "name": "qwen3-8b",
                "model_id": "Qwen/Qwen3-8B",
                "model_version_id": "model-version-1",
                "served_model_name": "qwen3-8b",
                "flavor": "1x1-mi355",
                "configuration": {"runtime": "sglang"},
            },
        )
    ]


def test_inference_lifecycle_and_observability_endpoints():
    api = FakeAPI()
    client = InferenceClient(api)

    client.stop_inference_instance("inf-1")
    client.restart_inference_instance("inf-1")
    client.finalize_inference_instance("inf-1")
    client.get_inference_instance_logs("inf-1", start_timestamp="2026-06-01T00:00:00Z")
    client.get_inference_instance_metrics("inf-1", end_timestamp="2026-06-01T01:00:00Z")

    assert api.calls == [
        (
            "POST",
            "/v1/Inference/StopInferenceInstance",
            {"inference_instance_id": "inf-1"},
        ),
        (
            "POST",
            "/v1/Inference/RestartInferenceInstance",
            {"inference_instance_id": "inf-1"},
        ),
        (
            "POST",
            "/v1/Inference/FinalizeInferenceInstance",
            {"inference_instance_id": "inf-1"},
        ),
        (
            "POST",
            "/v1/Inference/GetInferenceInstanceLogs",
            {
                "inference_instance_id": "inf-1",
                "start_timestamp": "2026-06-01T00:00:00Z",
            },
        ),
        (
            "POST",
            "/v1/Inference/GetInferenceInstanceMetrics",
            {
                "inference_instance_id": "inf-1",
                "end_timestamp": "2026-06-01T01:00:00Z",
            },
        ),
    ]


def test_inference_query_update_delete_and_endpoint_methods():
    api = FakeAPI()
    client = InferenceClient(api)

    client.list_inference_instances(
        page=1,
        limit=20,
        name="qwen",
        model_id="Qwen/Qwen3-8B",
        model_version_id="mv-1",
        status="RUNNING",
    )
    client.get_inference_instance("inf-1")
    client.update_inference_instance(
        inference_instance_id="inf-1",
        served_model_name="qwen3",
        clear_model_version_id=True,
        configuration={"runtime": "sglang"},
    )
    client.delete_inference_instance("inf-1")
    client.get_inference_instance_endpoint("inf-1")

    assert api.calls == [
        (
            "POST",
            "/v1/Inference/ListInferenceInstances",
            {
                "page": 1,
                "limit": 20,
                "name": "qwen",
                "model_id": "Qwen/Qwen3-8B",
                "model_version_id": "mv-1",
                "status": "RUNNING",
            },
        ),
        (
            "POST",
            "/v1/Inference/GetInferenceInstance",
            {"inference_instance_id": "inf-1"},
        ),
        (
            "POST",
            "/v1/Inference/UpdateInferenceInstance",
            {
                "inference_instance_id": "inf-1",
                "clear_model_version_id": True,
                "served_model_name": "qwen3",
                "configuration": {"runtime": "sglang"},
            },
        ),
        (
            "POST",
            "/v1/Inference/DeleteInferenceInstance",
            {"inference_instance_id": "inf-1"},
        ),
        (
            "POST",
            "/v1/Inference/GetInferenceInstanceEndpoint",
            {"inference_instance_id": "inf-1"},
        ),
    ]

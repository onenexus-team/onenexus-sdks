from nexusai.inference import InferenceClient
from nexusai.rpc_inference import RpcInferenceClient


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


def test_rpc_inference_create_instance_uses_id_based_pascal_case_endpoint():
    api = FakeAPI()
    client = RpcInferenceClient(api)

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


def test_rpc_inference_lifecycle_and_observability_endpoints():
    api = FakeAPI()
    client = RpcInferenceClient(api)

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


def test_rpc_inference_query_update_delete_and_endpoint_methods():
    api = FakeAPI()
    client = RpcInferenceClient(api)

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


def test_rest_inference_lifecycle_paths():
    api = FakeAPI()
    client = InferenceClient(api)

    client.stop_inference_instance("inf-1")
    client.restart_inference_instance("inf-1")
    client.finalize_inference_instance("inf-1")
    client.delete_inference_instance("inf-1")
    client.get_inference_instance_endpoint("inf-1")

    assert api.calls == [
        ("POST", "/v1/inference/instances/inf-1/stop", None),
        ("POST", "/v1/inference/instances/inf-1/restart", None),
        ("POST", "/v1/inference/instances/inf-1/finalize", None),
        ("DELETE", "/v1/inference/instances/inf-1", None),
        ("GET", "/v1/inference/instances/inf-1/endpoint", None),
    ]


def test_rest_inference_query_update_and_observability_paths():
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
    client.get_inference_instance_logs(
        "inf-1",
        start_timestamp="2026-06-01T00:00:00Z",
    )
    client.get_inference_instance_metrics(
        "inf-1",
        end_timestamp="2026-06-01T01:00:00Z",
    )

    assert api.calls == [
        (
            "GET",
            "/v1/inference/instances",
            {
                "page": 1,
                "limit": 20,
                "name": "qwen",
                "model_id": "Qwen/Qwen3-8B",
                "model_version_id": "mv-1",
                "status": "RUNNING",
            },
        ),
        ("GET", "/v1/inference/instances/inf-1", None),
        (
            "PATCH",
            "/v1/inference/instances/inf-1",
            {
                "clear_model_version_id": True,
                "served_model_name": "qwen3",
                "configuration": {"runtime": "sglang"},
            },
        ),
        (
            "GET",
            "/v1/inference/instances/inf-1/logs",
            {"start_timestamp": "2026-06-01T00:00:00Z"},
        ),
        (
            "GET",
            "/v1/inference/instances/inf-1/metrics",
            {"end_timestamp": "2026-06-01T01:00:00Z"},
        ),
    ]

from nexusai.rpc_training import RpcTrainingClient
from nexusai.training import TrainingClient


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


def test_rpc_training_create_run_uses_pascal_case_endpoint():
    api = FakeAPI()
    client = RpcTrainingClient(api)

    client.create_run(
        experiment_id="exp-1",
        name="run-1",
        dataset_id="dataset-1",
        training_type="pretraining",
        flavor="1x1-mi355",
        input_model_id="Qwen/Qwen3-8B",
        hyperparameters={"lr": 1e-5},
        num_checkpoint=2,
    )

    assert api.calls == [
        (
            "POST",
            "/v1/Training/CreateRun",
            {
                "experiment_id": "exp-1",
                "name": "run-1",
                "dataset_id": "dataset-1",
                "training_type": "pretraining",
                "flavor": "1x1-mi355",
                "input_model_id": "Qwen/Qwen3-8B",
                "hyperparameters": {"lr": 1e-5},
                "num_checkpoint": 2,
            },
        )
    ]


def test_rpc_training_resume_run_can_select_checkpoint():
    api = FakeAPI()
    client = RpcTrainingClient(api)

    client.resume_run(
        experiment_id="exp-1",
        run_id="run-1",
        checkpoint_name="ckpt-20",
        hyperparameters={"lr": 2e-5},
    )

    assert api.calls == [
        (
            "POST",
            "/v1/Training/ResumeRun",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-20",
                "hyperparameters": {"lr": 2e-5},
            },
        )
    ]


def test_rpc_training_monitoring_endpoints_return_iframe_payloads():
    api = FakeAPI()
    client = RpcTrainingClient(api)

    client.get_run_logs("exp-1", "run-1", start_timestamp="2026-06-01T00:00:00Z")
    client.get_run_metrics("exp-1", "run-1", end_timestamp="2026-06-01T01:00:00Z")

    assert api.calls == [
        (
            "POST",
            "/v1/Training/GetRunLogs",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "start_timestamp": "2026-06-01T00:00:00Z",
            },
        ),
        (
            "POST",
            "/v1/Training/GetRunMetrics",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "end_timestamp": "2026-06-01T01:00:00Z",
            },
        ),
    ]


def test_rpc_training_checkpoint_management_endpoints():
    api = FakeAPI()
    client = RpcTrainingClient(api)

    client.create_run_checkpoint("exp-1", "run-1", "ckpt-10")
    client.list_run_checkpoint_files("exp-1", "run-1", "ckpt-10")
    client.delete_run_checkpoint("exp-1", "run-1", "ckpt-10")
    client.create_checkpoint_upload_credential(
        "exp-1",
        "run-1",
        "ckpt-10",
        expires_in=900,
    )
    client.create_checkpoint_download_credential(
        "exp-1",
        "run-1",
        "ckpt-10",
        expires_in=900,
    )

    assert api.calls == [
        (
            "POST",
            "/v1/Training/CreateRunCheckpoint",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
            },
        ),
        (
            "POST",
            "/v1/Training/ListRunCheckpointFiles",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
            },
        ),
        (
            "POST",
            "/v1/Training/DeleteRunCheckpoint",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
            },
        ),
        (
            "POST",
            "/v1/Training/UploadRunCheckpoint",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
                "expires_in": 900,
            },
        ),
        (
            "POST",
            "/v1/Training/DownloadRunCheckpoint",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
                "expires_in": 900,
            },
        ),
    ]


def test_rest_training_run_lifecycle_paths():
    api = FakeAPI()
    client = TrainingClient(api)

    client.stop_run("exp-1", "run-1")
    client.cancel_run("exp-1", "run-1")
    client.resume_run("exp-1", "run-1")
    client.list_run_checkpoints("exp-1", "run-1")

    assert api.calls == [
        (
            "POST",
            "/v1/training/experiments/exp-1/runs/run-1/stop",
            None,
        ),
        (
            "POST",
            "/v1/training/experiments/exp-1/runs/run-1/cancel",
            None,
        ),
        (
            "POST",
            "/v1/training/experiments/exp-1/runs/run-1/resume",
            {},
        ),
        (
            "GET",
            "/v1/training/experiments/exp-1/runs/run-1/checkpoints",
            None,
        ),
    ]


def test_rest_training_checkpoint_management_paths():
    api = FakeAPI()
    client = TrainingClient(api)

    client.create_run_checkpoint("exp-1", "run-1", "ckpt-10")
    client.list_run_checkpoint_files("exp-1", "run-1", "ckpt-10")
    client.delete_run_checkpoint("exp-1", "run-1", "ckpt-10")
    client.create_checkpoint_upload_credential(
        "exp-1",
        "run-1",
        "ckpt-10",
        expires_in=900,
    )
    client.create_checkpoint_download_credential(
        "exp-1",
        "run-1",
        "ckpt-10",
        expires_in=900,
    )

    assert api.calls == [
        (
            "POST",
            "/v1/training/experiments/exp-1/runs/run-1/checkpoints",
            {"checkpoint_name": "ckpt-10"},
        ),
        (
            "GET",
            "/v1/training/experiments/exp-1/runs/run-1/checkpoints/ckpt-10/files",
            None,
        ),
        (
            "DELETE",
            "/v1/training/experiments/exp-1/runs/run-1/checkpoints/ckpt-10",
            None,
        ),
        (
            "POST",
            "/v1/training/experiments/exp-1/runs/run-1/checkpoints/ckpt-10/upload",
            {"expires_in": 900},
        ),
        (
            "POST",
            "/v1/training/experiments/exp-1/runs/run-1/checkpoints/ckpt-10/download",
            {"expires_in": 900},
        ),
    ]

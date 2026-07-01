from nexusai.rpc_training import RpcTrainingClient
from nexusai.internal_workload import WorkloadClient


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.post_dict = self.post
        self.post_optional_dict = self.post
        self.post_list = self.post

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


def test_rpc_training_get_run_tokenizer_accepts_missing_metadata():
    api = FakeAPI()
    api.post_optional_dict = lambda path, body=None: (
        api.calls.append(("POST", path, body)) or None
    )
    client = RpcTrainingClient(api)

    assert client.get_run_tokenizer("exp-1", "run-1") is None
    assert api.calls == [
        (
            "POST",
            "/v1/Training/GetRunTokenizer",
            {"experiment_id": "exp-1", "run_id": "run-1"},
        )
    ]


def test_rpc_training_checkpoint_management_endpoints():
    api = FakeAPI()
    client = RpcTrainingClient(api)

    client.start_checkpoint_upload(
        "exp-1",
        "run-1",
        "ckpt-10",
        num_process=2,
        process_index=1,
    )
    client.finalize_checkpoint_upload(
        "exp-1",
        "run-1",
        checkpoint_name="ckpt-10",
        process_index=1,
        file_count=2,
        total_size_bytes=20,
    )
    client.fail_checkpoint_upload("exp-1", "run-1", checkpoint_name="ckpt-10")
    client.cancel_checkpoint_upload("exp-1", "run-1", checkpoint_name="ckpt-10")
    client.list_run_checkpoint_files("exp-1", "run-1", "ckpt-10")
    client.delete_run_checkpoint("exp-1", "run-1", "ckpt-10")

    assert api.calls == [
        (
            "POST",
            "/v1/Training/StartCheckpointUpload",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
                "num_process": 2,
                "process_index": 1,
            },
        ),
        (
            "POST",
            "/v1/Training/FinalizeCheckpointUpload",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
                "process_index": 1,
                "file_count": 2,
                "total_size_bytes": 20,
            },
        ),
        (
            "POST",
            "/v1/Training/FailCheckpointUpload",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "ckpt-10",
            },
        ),
        (
            "POST",
            "/v1/Training/CancelCheckpointUpload",
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
    ]


def test_rpc_training_tokenizer_upload_endpoints():
    api = FakeAPI()
    client = RpcTrainingClient(api)

    client.start_run_tokenizer_upload(
        "exp-1",
        "run-1",
        execution_id="exec-1",
        storage_prefix="tokenizers/run-1",
    )
    client.finalize_run_tokenizer_upload(
        "exp-1",
        "run-1",
        file_count=3,
        total_size_bytes=30,
    )
    client.fail_run_tokenizer_upload("exp-1", "run-1", failure_reason="upload_error")
    client.cancel_run_tokenizer_upload("exp-1", "run-1")

    assert api.calls == [
        (
            "POST",
            "/v1/Training/StartRunTokenizerUpload",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "execution_id": "exec-1",
                "storage_prefix": "tokenizers/run-1",
                "file_count": 0,
                "total_size_bytes": 0,
            },
        ),
        (
            "POST",
            "/v1/Training/FinalizeRunTokenizerUpload",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "file_count": 3,
                "total_size_bytes": 30,
            },
        ),
        (
            "POST",
            "/v1/Training/FailRunTokenizerUpload",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "failure_reason": "upload_error",
            },
        ),
        (
            "POST",
            "/v1/Training/CancelRunTokenizerUpload",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
            },
        ),
    ]


def test_rpc_training_client_does_not_expose_reader_lease_methods():
    client = RpcTrainingClient(FakeAPI())

    assert not hasattr(client, "acquire_checkpoint_reader_lease")
    assert not hasattr(client, "heartbeat_checkpoint_reader_lease")
    assert not hasattr(client, "release_checkpoint_reader_lease")
    assert not hasattr(client, "acquire_run_tokenizer_reader_lease")
    assert not hasattr(client, "heartbeat_run_tokenizer_reader_lease")
    assert not hasattr(client, "release_run_tokenizer_reader_lease")


def test_internal_workload_training_reader_lease_endpoints():
    api = FakeAPI()
    client = WorkloadClient(api).training

    client.acquire_checkpoint_reader_lease(
        "exp-1",
        "run-1",
        checkpoint_name="step-10",
        execution_id="exec-1",
        owner_resource_type="model_version_conversion",
        owner_resource_id="version-1",
        owner_process_id="pod-1",
    )
    client.heartbeat_checkpoint_reader_lease("lease-1")
    client.release_checkpoint_reader_lease("lease-1")
    client.acquire_run_tokenizer_reader_lease(
        "exp-1",
        "run-1",
        owner_resource_type="training_run",
        owner_resource_id="run-1",
        owner_process_id="exec-1",
    )
    client.heartbeat_run_tokenizer_reader_lease("exp-1", "run-1", "lease-2")
    client.release_run_tokenizer_reader_lease("exp-1", "run-1", "lease-2")

    assert api.calls == [
        (
            "POST",
            "/v1/Training/AcquireRunCheckpointReaderLease",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "checkpoint_name": "step-10",
                "execution_id": "exec-1",
                "owner_resource_type": "model_version_conversion",
                "owner_resource_id": "version-1",
                "owner_process_id": "pod-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/v1/Training/HeartbeatRunCheckpointReaderLease",
            {"reader_lease_id": "lease-1", "lease_ttl_seconds": 3600},
        ),
        (
            "POST",
            "/v1/Training/ReleaseRunCheckpointReaderLease",
            {"reader_lease_id": "lease-1"},
        ),
        (
            "POST",
            "/v1/Training/AcquireRunTokenizerReaderLease",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "owner_resource_type": "training_run",
                "owner_resource_id": "run-1",
                "owner_process_id": "exec-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/v1/Training/HeartbeatRunTokenizerReaderLease",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "reader_lease_id": "lease-2",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/v1/Training/ReleaseRunTokenizerReaderLease",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "reader_lease_id": "lease-2",
            },
        ),
    ]


def test_internal_workload_data_hub_reader_lease_endpoints():
    api = FakeAPI()
    client = WorkloadClient(api).data_hub

    client.acquire_dataset_reader_lease(
        "dataset-1",
        owner_resource_type="training_run",
        owner_resource_id="run-1",
    )
    client.heartbeat_dataset_reader_lease("dataset-1", "lease-1")
    client.release_dataset_reader_lease("dataset-1", "lease-1")

    assert api.calls == [
        (
            "POST",
            "/v1/DataHub/AcquireDatasetReaderLease",
            {
                "dataset_id": "dataset-1",
                "owner_resource_type": "training_run",
                "owner_resource_id": "run-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/v1/DataHub/HeartbeatDatasetReaderLease",
            {
                "dataset_id": "dataset-1",
                "reader_lease_id": "lease-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/v1/DataHub/ReleaseDatasetReaderLease",
            {
                "dataset_id": "dataset-1",
                "reader_lease_id": "lease-1",
            },
        ),
    ]


def test_internal_workload_model_registry_reader_lease_endpoints():
    api = FakeAPI()
    client = WorkloadClient(api).model_registry

    client.acquire_model_version_reader_lease(
        "model-1",
        "version-1",
        owner_resource_type="inference_instance",
        owner_resource_id="inf-1",
        owner_process_id="pod-1",
    )
    client.heartbeat_model_version_reader_lease("model-1", "version-1", "lease-1")
    client.release_model_version_reader_lease("model-1", "version-1", "lease-1")

    assert api.calls == [
        (
            "POST",
            "/v1/ModelRegistry/AcquireModelVersionReaderLease",
            {
                "model_id": "model-1",
                "model_version_id": "version-1",
                "owner_resource_type": "inference_instance",
                "owner_resource_id": "inf-1",
                "owner_process_id": "pod-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/v1/ModelRegistry/HeartbeatModelVersionReaderLease",
            {
                "model_id": "model-1",
                "model_version_id": "version-1",
                "reader_lease_id": "lease-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/v1/ModelRegistry/ReleaseModelVersionReaderLease",
            {
                "model_id": "model-1",
                "model_version_id": "version-1",
                "reader_lease_id": "lease-1",
            },
        ),
    ]

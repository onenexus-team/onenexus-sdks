import inspect

import pytest

from nexusai import RetryPolicy
from nexusai._internal import training_transfer, workload as internal_workload
from nexusai._internal.training_transfer import TrainingTransferClient
from nexusai._internal.workload import InternalWorkloadClient
from nexusai._internal.storage import StorageTransferFile
from nexusai.training import TrainingClient


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.retry_policy = RetryPolicy(enabled=False)
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
    client = TrainingTransferClient(api)

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


def test_public_create_run_signature_does_not_expose_storage_paths():
    parameters = inspect.signature(TrainingClient.create_run).parameters

    assert "checkpoint_path" not in parameters
    assert "tokenizer_path" not in parameters


def test_rpc_training_resume_run_can_select_checkpoint():
    api = FakeAPI()
    client = TrainingTransferClient(api)

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
    client = TrainingTransferClient(api)

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
    client = TrainingTransferClient(api)

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
    client = TrainingTransferClient(api)

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
    client = TrainingTransferClient(api)

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
    client = TrainingTransferClient(FakeAPI())

    assert not hasattr(client, "acquire_checkpoint_reader_lease")
    assert not hasattr(client, "heartbeat_checkpoint_reader_lease")
    assert not hasattr(client, "release_checkpoint_reader_lease")
    assert not hasattr(client, "acquire_run_tokenizer_reader_lease")
    assert not hasattr(client, "heartbeat_run_tokenizer_reader_lease")
    assert not hasattr(client, "release_run_tokenizer_reader_lease")


def test_internal_workload_training_reader_lease_endpoints():
    api = FakeAPI()
    client = InternalWorkloadClient(api).training

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
            "/workload/v1/Training/AcquireRunCheckpointReaderLease",
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
            "/workload/v1/Training/HeartbeatRunCheckpointReaderLease",
            {"reader_lease_id": "lease-1", "lease_ttl_seconds": 3600},
        ),
        (
            "POST",
            "/workload/v1/Training/ReleaseRunCheckpointReaderLease",
            {"reader_lease_id": "lease-1"},
        ),
        (
            "POST",
            "/workload/v1/Training/AcquireRunTokenizerReaderLease",
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
            "/workload/v1/Training/HeartbeatRunTokenizerReaderLease",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "reader_lease_id": "lease-2",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/workload/v1/Training/ReleaseRunTokenizerReaderLease",
            {
                "experiment_id": "exp-1",
                "run_id": "run-1",
                "reader_lease_id": "lease-2",
            },
        ),
    ]


def test_internal_workload_data_hub_reader_lease_endpoints():
    api = FakeAPI()
    client = InternalWorkloadClient(api).data_hub

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
            "/workload/v1/DataHub/AcquireDatasetReaderLease",
            {
                "dataset_id": "dataset-1",
                "owner_resource_type": "training_run",
                "owner_resource_id": "run-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/workload/v1/DataHub/HeartbeatDatasetReaderLease",
            {
                "dataset_id": "dataset-1",
                "reader_lease_id": "lease-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/workload/v1/DataHub/ReleaseDatasetReaderLease",
            {
                "dataset_id": "dataset-1",
                "reader_lease_id": "lease-1",
            },
        ),
    ]


def test_internal_workload_model_registry_reader_lease_endpoints():
    api = FakeAPI()
    client = InternalWorkloadClient(api).model_registry

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
            "/workload/v1/ModelRegistry/AcquireModelVersionReaderLease",
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
            "/workload/v1/ModelRegistry/HeartbeatModelVersionReaderLease",
            {
                "model_id": "model-1",
                "model_version_id": "version-1",
                "reader_lease_id": "lease-1",
                "lease_ttl_seconds": 3600,
            },
        ),
        (
            "POST",
            "/workload/v1/ModelRegistry/ReleaseModelVersionReaderLease",
            {
                "model_id": "model-1",
                "model_version_id": "version-1",
                "reader_lease_id": "lease-1",
            },
        ),
    ]


def test_internal_workload_checkpoint_upload_uses_workload_lifecycle(
    monkeypatch, tmp_path
):
    class UploadAPI(FakeAPI):
        def post(self, path, body=None):
            self.calls.append(("POST", path, body))
            if path.endswith("StartCheckpointUpload"):
                return {"checkpoint_id": "checkpoint-1", "status": "UPLOADING"}
            if path.endswith("GetRunCheckpointTransferTarget"):
                return {
                    "resource_id": "checkpoint-1",
                    "bucket": "checkpoint-bucket",
                    "prefix": "run-1/step-10/process-0",
                }
            if path.endswith("FinalizeCheckpointUpload"):
                return {"checkpoint_id": "checkpoint-1", "status": "FINALIZED"}
            return {"ok": True}

    api = UploadAPI()
    source = tmp_path / "checkpoint"
    source.mkdir()
    monkeypatch.setattr(
        internal_workload,
        "create_runtime_s3_credential",
        lambda **_kwargs: {
            "bucket": "checkpoint-bucket",
            "prefix": "run-1/step-10/process-0",
        },
    )
    monkeypatch.setattr(
        internal_workload,
        "upload_path",
        lambda *_args, **_kwargs: [
            StorageTransferFile(
                local_path=str(source / "state.bin"),
                object_key="run-1/step-10/process-0/state.bin",
                relative_path="state.bin",
                size_bytes=12,
            )
        ],
    )
    client = InternalWorkloadClient(api, cas_client_factory=lambda: object()).training

    result = client.upload_to_checkpoint(
        experiment_id="exp-1",
        run_id="run-1",
        checkpoint_name="step-10",
        source_path=str(source),
        process_index=0,
        idempotency_key="run-1:step-10:0",
    )

    assert result.resource["status"] == "FINALIZED"
    assert [call[1] for call in api.calls] == [
        "/workload/v1/Training/StartCheckpointUpload",
        "/protected/v1/Training/GetRunCheckpointTransferTarget",
        "/workload/v1/Training/FinalizeCheckpointUpload",
    ]


def test_internal_workload_checkpoint_validator_runs_before_finalize(
    monkeypatch, tmp_path
):
    class UploadAPI(FakeAPI):
        def post(self, path, body=None):
            self.calls.append(("POST", path, body))
            if path.endswith("StartCheckpointUpload"):
                return {"checkpoint_id": "checkpoint-1", "status": "UPLOADING"}
            if path.endswith("GetRunCheckpointTransferTarget"):
                return {
                    "resource_id": "checkpoint-1",
                    "bucket": "checkpoint-bucket",
                    "prefix": "run-1/step-10",
                }
            if path.endswith("FailCheckpointUpload"):
                return {"checkpoint_id": "checkpoint-1", "status": "FAILED"}
            raise AssertionError(f"unexpected endpoint: {path}")

    api = UploadAPI()
    monkeypatch.setattr(
        internal_workload,
        "create_runtime_s3_credential",
        lambda **_kwargs: {
            "bucket": "checkpoint-bucket",
            "prefix": "run-1/step-10",
        },
    )
    monkeypatch.setattr(
        internal_workload,
        "upload_path",
        lambda *_args, **_kwargs: [
            StorageTransferFile(
                local_path=str(tmp_path / "state.bin"),
                object_key="run-1/step-10/state.bin",
                relative_path="state.bin",
                size_bytes=12,
            )
        ],
    )
    client = InternalWorkloadClient(api, cas_client_factory=lambda: object()).training

    with pytest.raises(RuntimeError, match="source changed"):
        client.upload_to_checkpoint(
            experiment_id="exp-1",
            run_id="run-1",
            checkpoint_name="step-10",
            source_path=str(tmp_path),
            validate_uploaded_files=lambda _files: (_ for _ in ()).throw(
                RuntimeError("source changed")
            ),
        )

    assert [call[1] for call in api.calls] == [
        "/workload/v1/Training/StartCheckpointUpload",
        "/protected/v1/Training/GetRunCheckpointTransferTarget",
        "/workload/v1/Training/FailCheckpointUpload",
    ]


def test_internal_workload_tokenizer_upload_uses_workload_lifecycle(
    monkeypatch, tmp_path
):
    class UploadAPI(FakeAPI):
        def post(self, path, body=None):
            self.calls.append(("POST", path, body))
            if path.endswith("StartRunTokenizerUpload"):
                return {"id": "tokenizer-1", "status": "UPLOADING"}
            if path.endswith("GetRunTokenizerTransferTarget"):
                return {
                    "resource_id": "tokenizer-1",
                    "bucket": "tokenizer-bucket",
                    "prefix": "run-1/tokenizer",
                }
            if path.endswith("FinalizeRunTokenizerUpload"):
                return {"id": "tokenizer-1", "status": "FINALIZED"}
            raise AssertionError(f"unexpected endpoint: {path}")

    api = UploadAPI()
    monkeypatch.setattr(
        internal_workload,
        "create_runtime_s3_credential",
        lambda **_kwargs: {
            "bucket": "tokenizer-bucket",
            "prefix": "run-1/tokenizer",
        },
    )
    monkeypatch.setattr(
        internal_workload,
        "upload_path",
        lambda *_args, **_kwargs: [
            StorageTransferFile(
                local_path=str(tmp_path / "tokenizer.json"),
                object_key="run-1/tokenizer/tokenizer.json",
                relative_path="tokenizer.json",
                size_bytes=18,
            )
        ],
    )
    client = InternalWorkloadClient(api, cas_client_factory=lambda: object()).training

    result = client.upload_to_run_tokenizer(
        experiment_id="exp-1",
        run_id="run-1",
        source_path=str(tmp_path),
    )

    assert result.resource["status"] == "FINALIZED"
    assert [call[1] for call in api.calls] == [
        "/workload/v1/Training/StartRunTokenizerUpload",
        "/protected/v1/Training/GetRunTokenizerTransferTarget",
        "/workload/v1/Training/FinalizeRunTokenizerUpload",
    ]
    assert api.calls[-1][2]["manifest"] == {
        "files": [{"path": "tokenizer.json", "size": 18}]
    }


def test_internal_workload_model_upload_uses_workload_lifecycle(monkeypatch, tmp_path):
    class UploadAPI(FakeAPI):
        def post(self, path, body=None):
            self.calls.append(("POST", path, body))
            if path.endswith("StartModelVersionUpload"):
                return {"id": "version-1", "status": "UPLOADING"}
            if path.endswith("GetModelVersionTransferTarget"):
                return {
                    "resource_id": "version-1",
                    "bucket": "model-bucket",
                    "prefix": "model-1/version-1",
                }
            if path.endswith("FinalizeModelVersionUpload"):
                return {"id": "version-1", "status": "FINALIZED"}
            raise AssertionError(f"unexpected endpoint: {path}")

    api = UploadAPI()
    monkeypatch.setattr(
        internal_workload,
        "create_runtime_s3_credential",
        lambda **_kwargs: {
            "bucket": "model-bucket",
            "prefix": "model-1/version-1",
        },
    )
    monkeypatch.setattr(
        internal_workload,
        "upload_path",
        lambda *_args, **_kwargs: [
            StorageTransferFile(
                local_path=str(tmp_path / "model.safetensors"),
                object_key="model-1/version-1/model.safetensors",
                relative_path="model.safetensors",
                size_bytes=128,
            )
        ],
    )
    client = InternalWorkloadClient(
        api, cas_client_factory=lambda: object()
    ).model_registry

    result = client.upload_to_model_version(
        model_id="model-1",
        model_version_id="version-1",
        source_path=str(tmp_path),
        artifact_format="safetensors",
    )

    assert result.resource["status"] == "FINALIZED"
    assert [call[1] for call in api.calls] == [
        "/workload/v1/ModelRegistry/StartModelVersionUpload",
        "/protected/v1/ModelRegistry/GetModelVersionTransferTarget",
        "/workload/v1/ModelRegistry/FinalizeModelVersionUpload",
    ]
    assert api.calls[-1][2]["manifest"] == {
        "files": [{"path": "model.safetensors", "size": 128}]
    }


def test_rpc_training_downloads_checkpoint_through_protected_target(
    monkeypatch, tmp_path
):
    class DownloadAPI(FakeAPI):
        def post(self, path, body=None):
            self.calls.append(("POST", path, body))
            if path.endswith("GetRunCheckpointTransferTarget"):
                return {
                    "resource_id": "checkpoint-1",
                    "bucket": "checkpoint-bucket",
                    "prefix": "run-1/step-10",
                }
            if path.endswith("GetRunCheckpoint"):
                return {"id": "checkpoint-1", "name": "step-10"}
            return {"ok": True}

    api = DownloadAPI()
    client = TrainingTransferClient(api, cas_client_factory=lambda: object())
    monkeypatch.setattr(
        client,
        "_create_runtime_s3_credential",
        lambda **_kwargs: {"bucket": "checkpoint-bucket", "prefix": "run-1/step-10"},
    )
    monkeypatch.setattr(
        training_transfer,
        "download_prefix",
        lambda *_args, **_kwargs: [
            StorageTransferFile(
                local_path=str(tmp_path / "state.bin"),
                object_key="run-1/step-10/state.bin",
                relative_path="state.bin",
                size_bytes=12,
            )
        ],
    )

    result = client.download_run_checkpoint(
        "exp-1",
        "run-1",
        str(tmp_path),
        checkpoint_name="step-10",
    )

    assert result.resource["id"] == "checkpoint-1"
    assert [call[1] for call in api.calls] == [
        "/protected/v1/Training/GetRunCheckpointTransferTarget",
        "/v1/Training/GetRunCheckpoint",
    ]


def test_rpc_training_downloads_tokenizer_through_protected_target(
    monkeypatch, tmp_path
):
    class DownloadAPI(FakeAPI):
        def post(self, path, body=None):
            self.calls.append(("POST", path, body))
            if path.endswith("GetRunTokenizerTransferTarget"):
                return {
                    "resource_id": "tokenizer-1",
                    "bucket": "tokenizer-bucket",
                    "prefix": "run-1/tokenizer",
                }
            if path.endswith("GetRunTokenizer"):
                return {"id": "tokenizer-1", "status": "FINALIZED"}
            return {"ok": True}

    api = DownloadAPI()
    client = TrainingTransferClient(api, cas_client_factory=lambda: object())
    monkeypatch.setattr(
        client,
        "_create_runtime_s3_credential",
        lambda **_kwargs: {"bucket": "tokenizer-bucket", "prefix": "run-1/tokenizer"},
    )
    monkeypatch.setattr(training_transfer, "download_prefix", lambda *_a, **_k: [])

    result = client.download_run_tokenizer("exp-1", "run-1", str(tmp_path))

    assert result.resource["id"] == "tokenizer-1"
    assert [call[1] for call in api.calls] == [
        "/v1/Training/GetRunTokenizer",
        "/protected/v1/Training/GetRunTokenizerTransferTarget",
    ]

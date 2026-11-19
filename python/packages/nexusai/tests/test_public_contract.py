from __future__ import annotations

from dataclasses import fields
import inspect
from typing import cast

from nexusai import (
    ActionResult,
    DataHubClient,
    DatasetDetail,
    DatasetSizeResult,
    DatasetSummary,
    InferenceClient,
    InferenceActionResult,
    InferenceInstanceDetail,
    InferenceInstanceSummary,
    InferenceLogsResult,
    InferenceMetricsResult,
    MessageCode,
    ModelDetail,
    ModelRegistryClient,
    ModelSummary,
    ModelVersionDetail,
    ModelVersionSizeResult,
    ModelVersionSummary,
    MonitoringResult,
    OneNexusClient,
    Page,
    RetryPolicy,
    RunCheckpoint,
    RunDetail,
    RunMonitoringResult,
    RunSummary,
    RunTokenizer,
    TenantWorkspaceDetail,
    TenantWorkspaceSummary,
    TrainingClient,
    TransferFile,
)
from nexusai._internal.http import APIClient, APIListEnvelope
from nexusai._internal.results import InternalUploadResult
from nexusai._internal.storage import StorageTransferFile


PROHIBITED = {
    "background_job_id",
    "bucket",
    "current_execution_id",
    "execution_id",
    "jobset_name",
    "k8s_namespace",
    "lease_id",
    "process_index",
    "retry_count",
    "secret",
    "session_id",
    "storage_prefix",
}


def names(model: type) -> set[str]:
    return {field.name for field in fields(model)}


def test_async_message_codes_are_public_constants() -> None:
    assert MessageCode.ASYNC_REQUEST_ACCEPTED == "ASYNC_REQUEST_ACCEPTED"
    assert MessageCode.WORKLOAD_IDENTITY_FAILED == "WORKLOAD_IDENTITY_FAILED"
    assert MessageCode.TRAINING_RUN_GPU_QUOTA_EXCEEDED == (
        "TRAINING_RUN_GPU_QUOTA_EXCEEDED"
    )
    assert MessageCode.INFERENCE_RESOURCE_SCHEDULING_TIMEOUT == (
        "INFERENCE_RESOURCE_SCHEDULING_TIMEOUT"
    )


def test_public_models_have_exact_bounded_fields() -> None:
    expected = {
        TenantWorkspaceSummary: {
            "id",
            "name",
            "status",
            "message_code",
            "num_models",
            "num_model_versions",
            "num_datasets",
            "num_experiments",
            "num_experiment_runs",
            "created_at",
            "updated_at",
        },
        TenantWorkspaceDetail: {
            "id",
            "name",
            "status",
            "message_code",
            "num_models",
            "num_model_versions",
            "num_datasets",
            "num_experiments",
            "num_experiment_runs",
            "created_at",
            "updated_at",
            "message",
            "extras_data",
        },
        DatasetSummary: {
            "id",
            "name",
            "status",
            "message_code",
            "status_message",
            "file_count",
            "total_size_bytes",
            "created_at",
            "updated_at",
        },
        DatasetDetail: {
            "id",
            "name",
            "status",
            "message_code",
            "status_message",
            "file_count",
            "total_size_bytes",
            "created_at",
            "updated_at",
            "extras_data",
        },
        ModelSummary: {
            "id",
            "name",
            "status",
            "message_code",
            "status_message",
            "source",
            "model_family",
            "hf_repo_id",
            "version_count",
            "created_at",
            "updated_at",
            "latest_version",
        },
        ModelDetail: {
            "id",
            "name",
            "status",
            "message_code",
            "status_message",
            "source",
            "model_family",
            "hf_repo_id",
            "version_count",
            "created_at",
            "updated_at",
            "latest_version",
            "inference_config",
            "extras_data",
        },
        ModelVersionSummary: {
            "id",
            "model_id",
            "name",
            "status",
            "message_code",
            "status_message",
            "file_count",
            "total_size_bytes",
            "created_at",
            "updated_at",
            "artifact_kind",
            "artifact_format",
            "finalized_at",
        },
        ModelVersionDetail: {
            "id",
            "model_id",
            "name",
            "status",
            "message_code",
            "status_message",
            "file_count",
            "total_size_bytes",
            "created_at",
            "updated_at",
            "artifact_kind",
            "artifact_format",
            "finalized_at",
            "source",
            "extras_data",
        },
        RunSummary: {
            "id",
            "name",
            "experiment",
            "dataset",
            "input_model",
            "training_type",
            "flavor",
            "status",
            "message_code",
            "created_at",
            "updated_at",
            "step",
            "attempt",
        },
        RunDetail: {
            "id",
            "name",
            "experiment",
            "dataset",
            "input_model",
            "training_type",
            "flavor",
            "status",
            "message_code",
            "created_at",
            "updated_at",
            "step",
            "attempt",
            "hyperparameters",
            "checkpoint_count",
            "output_model",
            "output_model_version",
            "message",
            "extras_data",
        },
        RunCheckpoint: {
            "id",
            "name",
            "status",
            "message_code",
            "status_message",
            "file_count",
            "size_bytes",
            "step",
            "source_attempt",
            "created_at",
            "updated_at",
        },
        RunTokenizer: {
            "id",
            "status",
            "message_code",
            "status_message",
            "file_count",
            "size_bytes",
            "created_at",
            "updated_at",
        },
        InferenceInstanceSummary: {
            "id",
            "name",
            "model",
            "served_model_name",
            "flavor",
            "status",
            "message_code",
            "status_detail",
            "created_at",
            "updated_at",
            "endpoint",
        },
        InferenceInstanceDetail: {
            "id",
            "name",
            "model",
            "served_model_name",
            "flavor",
            "status",
            "message_code",
            "status_detail",
            "created_at",
            "updated_at",
            "endpoint",
            "configuration",
            "operation_id",
            "message",
            "extras_data",
        },
        ActionResult: {
            "resource_id",
            "status",
            "message_code",
            "status_message",
        },
        InferenceActionResult: {
            "resource_id",
            "status",
            "message_code",
            "endpoint",
            "operation_id",
        },
        DatasetSizeResult: {"dataset_id", "object_count", "size_bytes", "size"},
        ModelVersionSizeResult: {
            "model_id",
            "model_version_id",
            "object_count",
            "size_bytes",
            "size",
        },
    }
    for model, field_names in expected.items():
        assert names(model) == field_names
        assert not (names(model) & PROHIBITED)


def test_nested_public_models_ignore_internal_response_fields() -> None:
    run = RunDetail.from_dict(
        {
            "id": "run-1",
            "name": "run",
            "experiment": {"id": "exp-1", "name": "experiment"},
            "dataset": {"id": "dataset-1", "name": "dataset"},
            "input_model": {
                "source": "platform",
                "model": {"id": "model-1", "name": "model"},
                "model_version": {"id": "version-1", "name": "v1"},
            },
            "training_type": "pretraining",
            "flavor": "2x2-mi355",
            "status": "RUNNING",
            "message_code": "TRAINING_RUN_RUNNING",
            "step": "TRAINING",
            "attempt": 2,
            "created_at": "2026-07-13T00:00:00Z",
            "updated_at": "2026-07-13T00:01:00Z",
            "hyperparameters": {"lr": 0.001},
            "checkpoint_count": 1,
            "current_execution_id": "must-not-leak",
            "jobset_name": "must-not-leak",
        }
    )
    assert run.input_model.model is not None
    assert run.input_model.model.id == "model-1"
    assert not hasattr(run, "current_execution_id")
    assert not hasattr(run, "jobset_name")


def test_monitoring_projection_parses_attempts_without_execution_ids() -> None:
    result = RunMonitoringResult.from_dict(
        {
            "run_id": "run-1",
            "run_name": "run",
            "overview": {
                "is_live": True,
                "available": True,
                "attempt_count": 2,
                "iframe_url": "https://monitoring.example/overall",
            },
            "attempts": [
                {
                    "attempt": 2,
                    "status": "RUNNING",
                    "status_message": "Running",
                    "started_at": "2026-07-13T00:00:00Z",
                    "is_live": True,
                    "available": True,
                    "iframe_url": "https://monitoring.example/attempt/2",
                    "execution_id": "must-not-leak",
                }
            ],
        }
    )
    assert result.overview.attempt_count == 2
    assert result.attempts[0].attempt == 2
    assert not hasattr(result.attempts[0], "execution_id")


def test_inference_monitoring_uses_bounded_log_and_metric_models() -> None:
    logs = InferenceLogsResult.from_dict(
        {
            "inference_instance_id": "inference-1",
            "inference_instance_name": "inference",
            "logs": ["ready"],
            "degraded": False,
            "namespace": "must-not-leak",
        }
    )
    metrics = InferenceMetricsResult.from_dict(
        {
            "inference_instance_id": "inference-1",
            "inference_instance_name": "inference",
            "metrics": {"requests": 1},
            "grafana_metrics_url": "https://monitoring.example/metrics",
            "execution_id": "must-not-leak",
        }
    )

    assert logs.logs == ["ready"]
    assert metrics.metrics == {"requests": 1}
    assert not hasattr(logs, "namespace")
    assert not hasattr(metrics, "execution_id")
    assert MonitoringResult is RunMonitoringResult


def test_page_preserves_envelope_metadata(monkeypatch) -> None:
    api = APIClient(token="token", base_url="https://api.example.test")
    monkeypatch.setattr(
        api,
        "post_list_envelope",
        lambda *_args, **_kwargs: APIListEnvelope(
            items=[
                {
                    "id": "dataset-1",
                    "name": "dataset",
                    "status": "READY",
                    "message_code": "DATASET_READY",
                    "status_message": "Ready",
                    "file_count": 1,
                    "total_size_bytes": 10,
                }
            ],
            message="success",
            total_pages=4,
            request_id="request-1",
        ),
    )

    page = api.post_page("/v1/DataHub/ListDatasets", DatasetSummary)

    assert isinstance(page, Page)
    assert page.total_pages == 4
    assert page.message == "success"
    assert page.request_id == "request-1"
    assert page[0].id == "dataset-1"


def test_public_client_uses_typed_domain_clients_and_no_workload_property() -> None:
    client = OneNexusClient(token="opaque", retry_policy=RetryPolicy(enabled=False))

    assert isinstance(client.data_hub, DataHubClient)
    assert isinstance(client.model_registry, ModelRegistryClient)
    assert isinstance(client.training, TrainingClient)
    assert isinstance(client.inference, InferenceClient)
    assert not hasattr(client, "workload")


def test_public_upload_lifecycle_signatures_hide_internal_fields() -> None:
    prohibited_parameters = {
        "declared_manifest",
        "file_count",
        "last_error",
        "lease_ttl_seconds",
        "manifest",
        "process_index",
        "process_name",
        "reserved_quota_bytes",
        "storage_bucket",
        "storage_prefix",
        "total_size_bytes",
    }
    operations = (
        DataHubClient.start_dataset_upload,
        DataHubClient.finalize_dataset_upload,
        DataHubClient.fail_dataset_upload,
        ModelRegistryClient.start_model_version_upload,
        ModelRegistryClient.finalize_model_version_upload,
        TrainingClient.upload_to_checkpoint,
        TrainingClient.upload_to_run_tokenizer,
    )

    for operation in operations:
        parameters = set(inspect.signature(operation).parameters)
        assert not parameters & prohibited_parameters


def test_public_delete_methods_accept_synchronous_no_content() -> None:
    class DeleteAPI:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str]]] = []

        def post_optional_model(self, path, _model, body=None):
            self.calls.append((path, body))
            return None

    api = DeleteAPI()
    typed_api = cast(APIClient, api)

    assert DataHubClient(typed_api).delete_dataset("dataset-1") is None
    assert ModelRegistryClient(typed_api).delete_model("model-1") is None
    assert (
        ModelRegistryClient(typed_api).delete_model_version("model-1", "version-1")
        is None
    )
    training = TrainingClient(typed_api)
    assert training.delete_experiment("experiment-1") is None
    assert training.delete_run("experiment-1", "run-1") is None
    assert training.delete_run_checkpoints("experiment-1", "run-1") is None
    assert training.delete_run_checkpoint("experiment-1", "run-1", "step-1") is None
    assert training.delete_run_tokenizer("experiment-1", "run-1") is None
    assert InferenceClient(typed_api).delete_inference_instance("inference-1") is None

    assert [path for path, _body in api.calls] == [
        "/v1/DataHub/DeleteDataset",
        "/v1/ModelRegistry/DeleteModel",
        "/v1/ModelRegistry/DeleteModelVersion",
        "/v1/Training/DeleteExperiment",
        "/v1/Training/DeleteRun",
        "/v1/Training/DeleteRunCheckpoints",
        "/v1/Training/DeleteRunCheckpoint",
        "/v1/Training/DeleteRunTokenizer",
        "/v1/Inference/DeleteInferenceInstance",
    ]


def test_public_transfer_file_does_not_expose_storage_scope() -> None:
    assert names(TransferFile) == {"path", "size_bytes"}
    assert not (names(TransferFile) & PROHIBITED)


def test_high_level_upload_projects_internal_storage_file(monkeypatch) -> None:
    client = DataHubClient(cast(APIClient, object()))
    monkeypatch.setattr(
        client._transfer,
        "upload_to_dataset",
        lambda *_args, **_kwargs: InternalUploadResult(
            resource={
                "id": "dataset-1",
                "name": "dataset",
                "status": "READY",
                "message_code": "DATASET_READY",
                "status_message": "Ready",
                "file_count": 1,
                "total_size_bytes": 12,
            },
            files=[
                StorageTransferFile(
                    local_path="/private/source/train.jsonl",
                    object_key="tenant/dataset-1/train.jsonl",
                    relative_path="train.jsonl",
                    size_bytes=12,
                )
            ],
        ),
    )

    result = client.upload_to_dataset("dataset-1", "/private/source")

    assert result.files == [TransferFile(path="train.jsonl", size_bytes=12)]
    assert not hasattr(result.files[0], "object_key")
    assert not hasattr(result.files[0], "local_path")

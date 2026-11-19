from collections.abc import Callable
from typing import Any, Optional

from ._internal.training_transfer import TrainingTransferClient
from .config import CAS_S3_ROLE_NAME, S3_ENDPOINT_URL
from ._internal.http import APIClient
from ._internal.results import to_public_transfer_files
from .models import (
    ActionResult,
    ExperimentDetail,
    ExperimentSummary,
    FileItem,
    RunMonitoringResult,
    Page,
    RunCheckpoint,
    RunDetail,
    RunOutputModel,
    RunSummary,
    RunTokenizer,
)
from .results import DownloadResult, UploadResult
from .wait import WaitPolicy, wait_for_status


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class TrainingClient:
    def __init__(
        self,
        api: APIClient,
        *,
        cas_client_factory: Callable[[], Any] | None = None,
        s3_endpoint_url: str = S3_ENDPOINT_URL,
        s3_role_name: str = CAS_S3_ROLE_NAME,
    ) -> None:
        self._api = api
        self._transfer = TrainingTransferClient(
            api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=s3_endpoint_url,
            s3_role_name=s3_role_name,
        )

    def create_experiment(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ExperimentDetail:
        return self._api.post_model(
            "/v1/Training/CreateExperiment",
            ExperimentDetail,
            body=_clean({"name": name, "extras_data": extras_data}),
        )

    def list_experiments(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[ExperimentSummary]:
        return self._api.post_page(
            "/v1/Training/ListExperiments",
            ExperimentSummary,
            body=_clean(
                {
                    "page": page,
                    "limit": limit,
                    "name": name,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ),
        )

    def get_experiment(self, experiment_id: str) -> ExperimentDetail:
        return self._api.post_model(
            "/v1/Training/GetExperiment",
            ExperimentDetail,
            body={"experiment_id": experiment_id},
        )

    def update_experiment(
        self,
        experiment_id: str,
        name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ExperimentDetail:
        return self._api.post_model(
            "/v1/Training/UpdateExperiment",
            ExperimentDetail,
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "name": name,
                    "extras_data": extras_data,
                }
            ),
        )

    def delete_experiment(self, experiment_id: str) -> Optional[ActionResult]:
        return self._api.post_optional_model(
            "/v1/Training/DeleteExperiment",
            ActionResult,
            body={"experiment_id": experiment_id},
        )

    def create_run(
        self,
        experiment_id: str,
        name: str,
        dataset_id: str,
        training_type: str,
        flavor: str,
        input_model_id: str,
        hyperparameters: dict[str, Any],
        input_model_version_id: Optional[str] = None,
        num_checkpoint: int = 0,
        output_model: Optional[RunOutputModel] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/Training/CreateRun",
            ActionResult,
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "name": name,
                    "dataset_id": dataset_id,
                    "training_type": training_type,
                    "flavor": flavor,
                    "input_model_id": input_model_id,
                    "input_model_version_id": input_model_version_id,
                    "hyperparameters": hyperparameters,
                    "num_checkpoint": num_checkpoint,
                    "output_model": (
                        output_model.to_dict() if output_model is not None else None
                    ),
                    "extras_data": extras_data,
                }
            ),
        )

    def list_runs(
        self,
        experiment_id: str,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        training_type: Optional[str] = None,
        dataset_name: Optional[str] = None,
        output_model_name: Optional[str] = None,
        output_model_version_name: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[RunSummary]:
        return self._api.post_page(
            "/v1/Training/ListExperimentRuns",
            RunSummary,
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "page": page,
                    "limit": limit,
                    "name": name,
                    "training_type": training_type,
                    "dataset_name": dataset_name,
                    "output_model_name": output_model_name,
                    "output_model_version_name": output_model_version_name,
                    "status": status,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ),
        )

    def get_run(self, experiment_id: str, run_id: str) -> RunDetail:
        return self._api.post_model(
            "/v1/Training/GetRun",
            RunDetail,
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def wait_for_run(
        self,
        experiment_id: str,
        run_id: str,
        *,
        target_statuses: set[str] | frozenset[str] = frozenset(
            {"COMPLETED", "FAILED", "CANCELED", "STOPPED"}
        ),
        policy: WaitPolicy | None = None,
    ) -> RunDetail:
        return wait_for_status(
            lambda: self.get_run(experiment_id, run_id),
            status_of=lambda run: run.status,
            target_statuses=target_statuses,
            policy=policy or WaitPolicy(),
            description=f"training run {run_id}",
        )

    def stop_run(self, experiment_id: str, run_id: str) -> ActionResult:
        return self._run_action("StopRun", experiment_id, run_id)

    def cancel_run(self, experiment_id: str, run_id: str) -> ActionResult:
        return self._run_action("CancelRun", experiment_id, run_id)

    def delete_run(
        self, experiment_id: str, run_id: str
    ) -> Optional[ActionResult]:
        return self._api.post_optional_model(
            "/v1/Training/DeleteRun",
            ActionResult,
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def resume_run(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: Optional[str] = None,
        hyperparameters: Optional[dict[str, Any]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/Training/ResumeRun",
            ActionResult,
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_name": checkpoint_name,
                    "hyperparameters": hyperparameters,
                    "extras_data": extras_data,
                }
            ),
        )

    def get_run_logs(
        self,
        experiment_id: str,
        run_id: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> RunMonitoringResult:
        return self._run_monitoring(
            "GetRunLogs",
            experiment_id,
            run_id,
            start_timestamp,
            end_timestamp,
        )

    def get_run_metrics(
        self,
        experiment_id: str,
        run_id: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> RunMonitoringResult:
        return self._run_monitoring(
            "GetRunMetrics",
            experiment_id,
            run_id,
            start_timestamp,
            end_timestamp,
        )

    def list_run_checkpoints(
        self,
        experiment_id: str,
        run_id: str,
    ) -> list[RunCheckpoint]:
        return [
            RunCheckpoint.from_dict(item)
            for item in self._api.post_list(
                "/v1/Training/ListRunCheckpoints",
                body={"experiment_id": experiment_id, "run_id": run_id},
            )
        ]

    def get_run_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_id: str,
    ) -> RunCheckpoint:
        return self._api.post_model(
            "/v1/Training/GetRunCheckpoint",
            RunCheckpoint,
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_id": checkpoint_id,
            },
        )

    def download_run_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        destination_path: str,
        *,
        checkpoint_id: Optional[str] = None,
        checkpoint_name: Optional[str] = None,
    ) -> DownloadResult[RunCheckpoint]:
        result = self._transfer.download_run_checkpoint(
            experiment_id,
            run_id,
            destination_path,
            checkpoint_id=checkpoint_id,
            checkpoint_name=checkpoint_name,
        )
        return DownloadResult(
            resource=RunCheckpoint.from_dict(result.resource),
            files=to_public_transfer_files(result.files),
        )

    def upload_to_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
        source_path: str,
        checkpoint_step: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> UploadResult[RunCheckpoint]:
        result = self._transfer.upload_to_checkpoint(
            experiment_id=experiment_id,
            run_id=run_id,
            checkpoint_name=checkpoint_name,
            source_path=source_path,
            checkpoint_step=checkpoint_step,
            idempotency_key=idempotency_key,
        )
        checkpoint_id = str(
            result.resource.get("resource_id") or result.resource.get("id") or ""
        )
        if not checkpoint_id:
            raise RuntimeError("Upload response did not contain a checkpoint ID")
        return UploadResult(
            resource=self.get_run_checkpoint(experiment_id, run_id, checkpoint_id),
            files=to_public_transfer_files(result.files),
        )

    def delete_run_checkpoints(
        self, experiment_id: str, run_id: str
    ) -> Optional[ActionResult]:
        return self._api.post_optional_model(
            "/v1/Training/DeleteRunCheckpoints",
            ActionResult,
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def list_run_checkpoint_files(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
    ) -> list[FileItem]:
        return [
            FileItem.from_dict(item)
            for item in self._api.post_list(
                "/v1/Training/ListRunCheckpointFiles",
                body={
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_name": checkpoint_name,
                },
            )
        ]

    def delete_run_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
    ) -> Optional[ActionResult]:
        return self._api.post_optional_model(
            "/v1/Training/DeleteRunCheckpoint",
            ActionResult,
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
            },
        )

    def get_run_tokenizer(
        self,
        experiment_id: str,
        run_id: str,
    ) -> Optional[RunTokenizer]:
        return self._api.post_optional_model(
            "/v1/Training/GetRunTokenizer",
            RunTokenizer,
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def download_run_tokenizer(
        self,
        experiment_id: str,
        run_id: str,
        destination_path: str,
    ) -> DownloadResult[RunTokenizer]:
        result = self._transfer.download_run_tokenizer(
            experiment_id,
            run_id,
            destination_path,
        )
        return DownloadResult(
            resource=RunTokenizer.from_dict(result.resource),
            files=to_public_transfer_files(result.files),
        )

    def upload_to_run_tokenizer(
        self,
        experiment_id: str,
        run_id: str,
        source_path: str,
    ) -> UploadResult[RunTokenizer]:
        result = self._transfer.upload_to_run_tokenizer(
            experiment_id=experiment_id,
            run_id=run_id,
            source_path=source_path,
        )
        tokenizer = self.get_run_tokenizer(experiment_id, run_id)
        if tokenizer is None:
            raise RuntimeError("Uploaded tokenizer could not be resolved")
        return UploadResult(
            resource=tokenizer,
            files=to_public_transfer_files(result.files),
        )

    def delete_run_tokenizer(
        self, experiment_id: str, run_id: str
    ) -> Optional[ActionResult]:
        return self._api.post_optional_model(
            "/v1/Training/DeleteRunTokenizer",
            ActionResult,
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def _run_action(
        self,
        operation: str,
        experiment_id: str,
        run_id: str,
    ) -> ActionResult:
        return self._api.post_model(
            f"/v1/Training/{operation}",
            ActionResult,
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def _run_monitoring(
        self,
        operation: str,
        experiment_id: str,
        run_id: str,
        start_timestamp: Optional[str],
        end_timestamp: Optional[str],
    ) -> RunMonitoringResult:
        return self._api.post_model(
            f"/v1/Training/{operation}",
            RunMonitoringResult,
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                }
            ),
        )

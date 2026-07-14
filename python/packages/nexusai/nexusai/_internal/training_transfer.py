from collections.abc import Callable, Iterable
from typing import Any, Optional

from .cas_storage import create_runtime_s3_credential
from ..config import CAS_S3_ROLE_NAME, S3_ENDPOINT_URL
from .http import APIClient
from .results import (
    InternalDownloadResult as DownloadResult,
    InternalUploadResult as UploadResult,
)
from .storage import StorageTransferFile, download_prefix, upload_path


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class TrainingTransferClient:
    def __init__(
        self,
        api: APIClient,
        *,
        cas_client_factory: Callable[[], Any] | None = None,
        s3_endpoint_url: str = S3_ENDPOINT_URL,
        s3_role_name: str = CAS_S3_ROLE_NAME,
    ):
        self._api = api
        self._cas_client_factory = cas_client_factory
        self._s3_endpoint_url = s3_endpoint_url
        self._s3_role_name = s3_role_name

    def create_experiment(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/CreateExperiment",
            body=_clean({"name": name, "extras_data": extras_data}),
        )

    def list_experiments(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/Training/ListExperiments",
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

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/GetExperiment",
            body={"experiment_id": experiment_id},
        )

    def update_experiment(
        self,
        experiment_id: str,
        name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/UpdateExperiment",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "name": name,
                    "extras_data": extras_data,
                }
            ),
        )

    def delete_experiment(self, experiment_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/DeleteExperiment",
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
        output_model_name: Optional[str] = None,
        output_model_version_name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/CreateRun",
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
                    "output_model_name": output_model_name,
                    "output_model_version_name": output_model_version_name,
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
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/Training/ListExperimentRuns",
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

    def get_run(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/GetRun",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def stop_run(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/StopRun",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def cancel_run(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/CancelRun",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def delete_run(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/DeleteRun",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def resume_run(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: Optional[str] = None,
        hyperparameters: Optional[dict[str, Any]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/ResumeRun",
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
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/GetRunLogs",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                }
            ),
        )

    def get_run_metrics(
        self,
        experiment_id: str,
        run_id: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/GetRunMetrics",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                }
            ),
        )

    def list_run_checkpoints(
        self,
        experiment_id: str,
        run_id: str,
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/Training/ListRunCheckpoints",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def get_run_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_id: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/GetRunCheckpoint",
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
    ) -> DownloadResult[dict[str, Any]]:
        if not checkpoint_id and not checkpoint_name:
            raise ValueError("checkpoint_id or checkpoint_name is required")
        target = self._api.post_dict(
            "/protected/v1/Training/GetRunCheckpointTransferTarget",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_name": checkpoint_name,
                }
            ),
        )
        resolved_id = str(target["resource_id"])
        checkpoint = self.get_run_checkpoint(experiment_id, run_id, resolved_id)
        credential = self._create_runtime_s3_credential(
            bucket=str(target["bucket"]),
            prefix=str(target["prefix"]),
        )
        return DownloadResult(
            resource=checkpoint,
            files=download_prefix(destination_path, credential),
        )

    def start_checkpoint_upload(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
        execution_id: Optional[str] = None,
        attempt: Optional[int] = None,
        checkpoint_step: Optional[int] = None,
        num_process: int = 1,
        process_index: Optional[int] = None,
        process_name: Optional[str] = None,
        pod_name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        storage_bucket: Optional[str] = None,
        storage_prefix: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/StartCheckpointUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_name": checkpoint_name,
                    "execution_id": execution_id,
                    "attempt": attempt,
                    "checkpoint_step": checkpoint_step,
                    "num_process": num_process,
                    "process_index": process_index,
                    "process_name": process_name,
                    "pod_name": pod_name,
                    "idempotency_key": idempotency_key,
                    "storage_bucket": storage_bucket,
                    "storage_prefix": storage_prefix,
                }
            ),
        )

    def finalize_checkpoint_upload(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        process_index: Optional[int] = None,
        process_name: Optional[str] = None,
        pod_name: Optional[str] = None,
        storage_prefix: Optional[str] = None,
        manifest: Optional[dict[str, Any]] = None,
        file_count: int = 0,
        total_size_bytes: int = 0,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/FinalizeCheckpointUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_name": checkpoint_name,
                    "checkpoint_id": checkpoint_id,
                    "execution_id": execution_id,
                    "process_index": process_index,
                    "process_name": process_name,
                    "pod_name": pod_name,
                    "storage_prefix": storage_prefix,
                    "manifest": manifest,
                    "file_count": file_count,
                    "total_size_bytes": total_size_bytes,
                    "idempotency_key": idempotency_key,
                }
            ),
        )

    def fail_checkpoint_upload(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        process_index: Optional[int] = None,
        process_name: Optional[str] = None,
        pod_name: Optional[str] = None,
        storage_prefix: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/FailCheckpointUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_name": checkpoint_name,
                    "checkpoint_id": checkpoint_id,
                    "execution_id": execution_id,
                    "process_index": process_index,
                    "process_name": process_name,
                    "pod_name": pod_name,
                    "storage_prefix": storage_prefix,
                    "idempotency_key": idempotency_key,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def cancel_checkpoint_upload(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        process_index: Optional[int] = None,
        process_name: Optional[str] = None,
        pod_name: Optional[str] = None,
        storage_prefix: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/CancelCheckpointUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_name": checkpoint_name,
                    "checkpoint_id": checkpoint_id,
                    "execution_id": execution_id,
                    "process_index": process_index,
                    "process_name": process_name,
                    "pod_name": pod_name,
                    "storage_prefix": storage_prefix,
                    "idempotency_key": idempotency_key,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def upload_to_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
        source_path: str,
        execution_id: Optional[str] = None,
        attempt: Optional[int] = None,
        checkpoint_step: Optional[int] = None,
        num_process: int = 1,
        process_index: int = 0,
        process_name: Optional[str] = None,
        pod_name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        storage_bucket: Optional[str] = None,
        storage_prefix: Optional[str] = None,
    ) -> UploadResult[dict[str, Any]]:
        checkpoint = self.start_checkpoint_upload(
            experiment_id=experiment_id,
            run_id=run_id,
            checkpoint_name=checkpoint_name,
            execution_id=execution_id,
            attempt=attempt,
            checkpoint_step=checkpoint_step,
            num_process=num_process,
            process_index=process_index,
            process_name=process_name,
            pod_name=pod_name,
            idempotency_key=idempotency_key,
            storage_bucket=storage_bucket,
            storage_prefix=storage_prefix,
        )
        if checkpoint.get("status") == "FINALIZED":
            return UploadResult(resource=checkpoint, files=[])

        target = self._api.post_dict(
            "/protected/v1/Training/GetRunCheckpointTransferTarget",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
                "checkpoint_id": checkpoint.get("resource_id"),
            },
        )
        resolved_prefix = str(target["prefix"])
        credential = self._create_runtime_s3_credential(
            bucket=str(target["bucket"]),
            prefix=resolved_prefix,
        )
        try:
            files = upload_path(source_path, credential)
            finalized = self.finalize_checkpoint_upload(
                experiment_id=experiment_id,
                run_id=run_id,
                checkpoint_name=checkpoint_name,
                checkpoint_id=checkpoint.get("resource_id"),
                execution_id=execution_id,
                process_index=process_index,
                process_name=process_name,
                pod_name=pod_name,
                storage_prefix=resolved_prefix,
                manifest=_manifest_from_uploaded_files(
                    files,
                    prefix=credential["prefix"],
                ),
                file_count=len(files),
                total_size_bytes=sum(int(file.size_bytes) for file in files),
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            self._fail_checkpoint_upload_best_effort(
                experiment_id=experiment_id,
                run_id=run_id,
                checkpoint_name=checkpoint_name,
                checkpoint_id=checkpoint.get("resource_id"),
                execution_id=execution_id,
                process_index=process_index,
                process_name=process_name,
                pod_name=pod_name,
                storage_prefix=resolved_prefix,
                idempotency_key=idempotency_key,
                error=exc,
            )
            raise
        return UploadResult(resource=finalized, files=files)

    def fail_run_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_id: str,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/FailRunCheckpoint",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_id": checkpoint_id,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def delete_run_checkpoints(
        self,
        experiment_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/DeleteRunCheckpoints",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def list_run_checkpoint_files(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/Training/ListRunCheckpointFiles",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
            },
        )

    def delete_run_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/DeleteRunCheckpoint",
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
    ) -> Optional[dict[str, Any]]:
        return self._api.post_optional_dict(
            "/v1/Training/GetRunTokenizer",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def download_run_tokenizer(
        self,
        experiment_id: str,
        run_id: str,
        destination_path: str,
    ) -> DownloadResult[dict[str, Any]]:
        tokenizer = self.get_run_tokenizer(experiment_id, run_id)
        if tokenizer is None:
            raise RuntimeError("Run tokenizer does not exist")
        target = self._api.post_dict(
            "/protected/v1/Training/GetRunTokenizerTransferTarget",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )
        credential = self._create_runtime_s3_credential(
            bucket=str(target["bucket"]),
            prefix=str(target["prefix"]),
        )
        return DownloadResult(
            resource=tokenizer,
            files=download_prefix(destination_path, credential),
        )

    def start_run_tokenizer_upload(
        self,
        experiment_id: str,
        run_id: str,
        execution_id: Optional[str] = None,
        attempt: Optional[int] = None,
        storage_bucket: Optional[str] = None,
        storage_prefix: Optional[str] = None,
        manifest: Optional[dict[str, Any]] = None,
        file_count: int = 0,
        total_size_bytes: int = 0,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/StartRunTokenizerUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "execution_id": execution_id,
                    "attempt": attempt,
                    "storage_bucket": storage_bucket,
                    "storage_prefix": storage_prefix,
                    "manifest": manifest,
                    "file_count": file_count,
                    "total_size_bytes": total_size_bytes,
                }
            ),
        )

    def finalize_run_tokenizer_upload(
        self,
        experiment_id: str,
        run_id: str,
        manifest: Optional[dict[str, Any]] = None,
        file_count: int = 0,
        total_size_bytes: int = 0,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/FinalizeRunTokenizerUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "manifest": manifest,
                    "file_count": file_count,
                    "total_size_bytes": total_size_bytes,
                }
            ),
        )

    def fail_run_tokenizer_upload(
        self,
        experiment_id: str,
        run_id: str,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/FailRunTokenizerUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def cancel_run_tokenizer_upload(
        self,
        experiment_id: str,
        run_id: str,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/CancelRunTokenizerUpload",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def upload_to_run_tokenizer(
        self,
        experiment_id: str,
        run_id: str,
        source_path: str,
        execution_id: Optional[str] = None,
        attempt: Optional[int] = None,
        storage_bucket: Optional[str] = None,
        storage_prefix: Optional[str] = None,
    ) -> UploadResult[dict[str, Any]]:
        tokenizer = self.start_run_tokenizer_upload(
            experiment_id=experiment_id,
            run_id=run_id,
            execution_id=execution_id,
            attempt=attempt,
            storage_bucket=storage_bucket,
            storage_prefix=storage_prefix,
        )
        if tokenizer.get("status") == "FINALIZED":
            return UploadResult(resource=tokenizer, files=[])

        target = self._api.post_dict(
            "/protected/v1/Training/GetRunTokenizerTransferTarget",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )
        resolved_prefix = str(target["prefix"])
        credential = self._create_runtime_s3_credential(
            bucket=str(target["bucket"]),
            prefix=resolved_prefix,
        )
        try:
            files = upload_path(source_path, credential)
            finalized = self.finalize_run_tokenizer_upload(
                experiment_id=experiment_id,
                run_id=run_id,
                manifest=_manifest_from_uploaded_files(
                    files,
                    prefix=credential["prefix"],
                ),
                file_count=len(files),
                total_size_bytes=sum(int(file.size_bytes) for file in files),
            )
        except Exception as exc:
            try:
                self.fail_run_tokenizer_upload(
                    experiment_id=experiment_id,
                    run_id=run_id,
                    failure_reason=type(exc).__name__,
                    failure_message=str(exc),
                )
            except Exception:
                pass
            raise
        return UploadResult(resource=finalized, files=files)

    def delete_run_tokenizer(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/DeleteRunTokenizer",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def _create_runtime_s3_credential(
        self,
        *,
        bucket: Optional[str],
        prefix: Optional[str],
    ) -> dict[str, Any]:
        if not bucket:
            raise ValueError("transfer target bucket is required")
        if not prefix:
            raise ValueError("transfer target prefix is required")
        return create_runtime_s3_credential(
            cas_client_factory=self._cas_client_factory,
            role_name=self._s3_role_name,
            endpoint_url=self._s3_endpoint_url,
            bucket=bucket,
            prefix=prefix,
            retry_policy=self._api.retry_policy,
        )

    def _fail_checkpoint_upload_best_effort(
        self,
        *,
        experiment_id: str,
        run_id: str,
        checkpoint_name: Optional[str],
        checkpoint_id: Optional[str],
        execution_id: Optional[str],
        process_index: int,
        process_name: Optional[str],
        pod_name: Optional[str],
        storage_prefix: Optional[str],
        idempotency_key: Optional[str],
        error: Exception,
    ) -> None:
        try:
            self.fail_checkpoint_upload(
                experiment_id=experiment_id,
                run_id=run_id,
                checkpoint_name=checkpoint_name,
                checkpoint_id=checkpoint_id,
                execution_id=execution_id,
                process_index=process_index,
                process_name=process_name,
                pod_name=pod_name,
                storage_prefix=storage_prefix,
                idempotency_key=idempotency_key,
                failure_reason=type(error).__name__,
                failure_message=str(error),
            )
        except Exception:
            pass


def _manifest_from_uploaded_files(
    files: Iterable[StorageTransferFile],
    prefix: str,
) -> dict[str, Any]:
    return {
        "files": [
            {
                "path": _relative_object_key(file.object_key, prefix),
                "size": int(file.size_bytes),
            }
            for file in files
        ]
    }


def _relative_object_key(object_key: str, prefix: str) -> str:
    normalized_prefix = str(prefix or "").strip("/")
    normalized_key = str(object_key or "").strip("/")
    folder = f"{normalized_prefix}/" if normalized_prefix else ""
    if folder and normalized_key.startswith(folder):
        return normalized_key[len(folder) :]
    return normalized_key

from collections.abc import Callable, Iterable
from typing import Any, Optional

from .cas_storage import create_runtime_s3_credential
from .config import CAS_S3_ROLE_NAME, S3_ENDPOINT_URL
from .http import APIClient
from .results import UploadResult
from .storage import StorageTransferFile, upload_path


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class RpcTrainingClient:
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
        checkpoint_path: Optional[str] = None,
        tokenizer_path: Optional[str] = None,
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
                    "checkpoint_path": checkpoint_path,
                    "tokenizer_path": tokenizer_path,
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
    ) -> UploadResult:
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
        if checkpoint.get("should_upload") is False:
            return UploadResult(resource=checkpoint, files=[])

        resolved_bucket = storage_bucket or checkpoint.get("storage_bucket")
        resolved_prefix = storage_prefix or checkpoint.get("storage_prefix")
        credential = self._create_runtime_s3_credential(
            bucket=resolved_bucket,
            prefix=resolved_prefix,
            workspace_bucket_field="checkpoint_bucket",
        )
        try:
            files = upload_path(source_path, credential)
            finalized = self.finalize_checkpoint_upload(
                experiment_id=experiment_id,
                run_id=run_id,
                checkpoint_name=checkpoint_name,
                checkpoint_id=checkpoint.get("checkpoint_id"),
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
                checkpoint_id=checkpoint.get("checkpoint_id"),
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
    ) -> UploadResult:
        tokenizer = self.start_run_tokenizer_upload(
            experiment_id=experiment_id,
            run_id=run_id,
            execution_id=execution_id,
            attempt=attempt,
            storage_bucket=storage_bucket,
            storage_prefix=storage_prefix,
        )
        if tokenizer.get("should_upload") is False:
            return UploadResult(resource=tokenizer, files=[])

        resolved_bucket = storage_bucket or tokenizer.get("storage_bucket")
        resolved_prefix = storage_prefix or tokenizer.get("storage_prefix")
        credential = self._create_runtime_s3_credential(
            bucket=resolved_bucket,
            prefix=resolved_prefix,
            workspace_bucket_field="tokenizer_bucket",
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
        workspace_bucket_field: str,
    ) -> dict[str, Any]:
        resolved_bucket = bucket
        if not resolved_bucket:
            workspace = self._resolve_tenant_workspace()
            resolved_bucket = workspace.get(workspace_bucket_field)
        if not resolved_bucket:
            raise ValueError(f"Tenant workspace does not expose {workspace_bucket_field}")
        if not prefix:
            raise ValueError("storage prefix is required")
        return create_runtime_s3_credential(
            cas_client_factory=self._cas_client_factory,
            role_name=self._s3_role_name,
            endpoint_url=self._s3_endpoint_url,
            bucket=resolved_bucket,
            prefix=prefix,
        )

    def _resolve_tenant_workspace(self) -> dict[str, Any]:
        response = self._api.post(
            "/v1/TenantWorkspace/ListTenantWorkspaces",
            body={"page": 1, "limit": 1},
        )
        workspaces = _items(response)
        if not workspaces:
            raise ValueError("No tenant workspace is available for training storage")
        return workspaces[0]

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


def _items(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for key in ("items", "data", "results", "tenant_workspaces"):
            value = response.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested_items = value.get("items")
                if isinstance(nested_items, list):
                    return nested_items
    return []

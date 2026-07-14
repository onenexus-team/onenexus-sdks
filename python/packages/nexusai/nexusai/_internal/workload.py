from collections.abc import Callable, Iterable
from typing import Any, Optional

from .cas_storage import create_runtime_s3_credential
from ..config import CAS_S3_ROLE_NAME, S3_ENDPOINT_URL
from .http import APIClient
from .results import InternalUploadResult as UploadResult
from .storage import StorageTransferFile, upload_path


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class DataHubWorkloadClient:
    def __init__(self, api: APIClient):
        self._api = api

    def start_dataset_upload(
        self,
        dataset_id: str,
        *,
        idempotency_key: Optional[str] = None,
        declared_manifest: Optional[dict[str, Any]] = None,
        reserved_quota_bytes: int = 0,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/DataHub/StartDatasetUpload",
            body=_clean(
                {
                    "dataset_id": dataset_id,
                    "idempotency_key": idempotency_key,
                    "declared_manifest": declared_manifest,
                    "reserved_quota_bytes": reserved_quota_bytes,
                    "lease_ttl_seconds": lease_ttl_seconds,
                }
            ),
        )

    def finalize_dataset_upload(
        self,
        dataset_id: str,
        *,
        manifest: Optional[dict[str, Any]] = None,
        file_count: int = 0,
        total_size_bytes: int = 0,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/DataHub/FinalizeDatasetUpload",
            body=_clean(
                {
                    "dataset_id": dataset_id,
                    "manifest": manifest,
                    "file_count": file_count,
                    "total_size_bytes": total_size_bytes,
                }
            ),
        )

    def fail_dataset_upload(
        self,
        dataset_id: str,
        *,
        failure_reason: str,
        last_error: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/DataHub/FailDatasetUpload",
            body=_clean(
                {
                    "dataset_id": dataset_id,
                    "failure_reason": failure_reason,
                    "last_error": last_error,
                }
            ),
        )

    def cancel_dataset_upload(
        self,
        dataset_id: str,
        *,
        cancel_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/DataHub/CancelDatasetUpload",
            body=_clean(
                {
                    "dataset_id": dataset_id,
                    "cancel_reason": cancel_reason,
                }
            ),
        )

    def acquire_dataset_reader_lease(
        self,
        dataset_id: str,
        owner_resource_type: str,
        owner_resource_id: str,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/DataHub/AcquireDatasetReaderLease",
            body={
                "dataset_id": dataset_id,
                "owner_resource_type": owner_resource_type,
                "owner_resource_id": owner_resource_id,
                "lease_ttl_seconds": lease_ttl_seconds,
            },
        )

    def heartbeat_dataset_reader_lease(
        self,
        dataset_id: str,
        reader_lease_id: str,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/DataHub/HeartbeatDatasetReaderLease",
            body={
                "dataset_id": dataset_id,
                "reader_lease_id": reader_lease_id,
                "lease_ttl_seconds": lease_ttl_seconds,
            },
        )

    def release_dataset_reader_lease(
        self,
        dataset_id: str,
        reader_lease_id: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/DataHub/ReleaseDatasetReaderLease",
            body={
                "dataset_id": dataset_id,
                "reader_lease_id": reader_lease_id,
            },
        )


class ModelRegistryWorkloadClient:
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

    def start_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        *,
        idempotency_key: Optional[str] = None,
        declared_manifest: Optional[dict[str, Any]] = None,
        reserved_quota_bytes: int = 0,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/ModelRegistry/StartModelVersionUpload",
            body=_clean(
                {
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "idempotency_key": idempotency_key,
                    "declared_manifest": declared_manifest,
                    "reserved_quota_bytes": reserved_quota_bytes,
                }
            ),
        )

    def finalize_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        *,
        manifest: Optional[dict[str, Any]] = None,
        file_count: int = 0,
        total_size_bytes: int = 0,
        artifact_format: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/ModelRegistry/FinalizeModelVersionUpload",
            body=_clean(
                {
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "manifest": manifest,
                    "file_count": file_count,
                    "total_size_bytes": total_size_bytes,
                    "artifact_format": artifact_format,
                }
            ),
        )

    def fail_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        *,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/ModelRegistry/FailModelVersionUpload",
            body=_clean(
                {
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def cancel_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        *,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/ModelRegistry/CancelModelVersionUpload",
            body=_clean(
                {
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def upload_to_model_version(
        self,
        model_id: str,
        model_version_id: str,
        source_path: str,
        *,
        idempotency_key: Optional[str] = None,
        artifact_format: Optional[str] = None,
    ) -> UploadResult[dict[str, Any]]:
        version = self.start_model_version_upload(
            model_id,
            model_version_id,
            idempotency_key=idempotency_key,
        )
        if str(version.get("status", "")).upper() in {"FINALIZED", "READY"}:
            return UploadResult(resource=version, files=[])

        target = self._api.post_dict(
            "/protected/v1/ModelRegistry/GetModelVersionTransferTarget",
            body={"model_id": model_id, "model_version_id": model_version_id},
        )
        credential = self._runtime_credential(target)
        try:
            files = upload_path(source_path, credential)
            finalized = self.finalize_model_version_upload(
                model_id,
                model_version_id,
                manifest=_manifest_from_uploaded_files(files, credential["prefix"]),
                file_count=len(files),
                total_size_bytes=sum(file.size_bytes for file in files),
                artifact_format=artifact_format,
            )
        except Exception as error:
            try:
                self.fail_model_version_upload(
                    model_id,
                    model_version_id,
                    failure_reason=type(error).__name__,
                    failure_message=str(error),
                )
            except Exception:
                pass
            raise
        return UploadResult(resource=finalized, files=files)

    def _runtime_credential(self, target: dict[str, Any]) -> dict[str, Any]:
        if self._cas_client_factory is None:
            raise RuntimeError("CAS client is required for workload storage transfer")
        return create_runtime_s3_credential(
            cas_client_factory=self._cas_client_factory,
            role_name=self._s3_role_name,
            endpoint_url=self._s3_endpoint_url,
            bucket=str(target["bucket"]),
            prefix=str(target["prefix"]),
            retry_policy=self._api.retry_policy,
        )

    def acquire_model_version_reader_lease(
        self,
        model_id: str,
        model_version_id: str,
        owner_resource_type: str,
        owner_resource_id: str,
        owner_process_id: Optional[str] = None,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/ModelRegistry/AcquireModelVersionReaderLease",
            body=_clean(
                {
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "owner_resource_type": owner_resource_type,
                    "owner_resource_id": owner_resource_id,
                    "owner_process_id": owner_process_id,
                    "lease_ttl_seconds": lease_ttl_seconds,
                }
            ),
        )

    def heartbeat_model_version_reader_lease(
        self,
        model_id: str,
        model_version_id: str,
        reader_lease_id: str,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/ModelRegistry/HeartbeatModelVersionReaderLease",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "reader_lease_id": reader_lease_id,
                "lease_ttl_seconds": lease_ttl_seconds,
            },
        )

    def release_model_version_reader_lease(
        self,
        model_id: str,
        model_version_id: str,
        reader_lease_id: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/ModelRegistry/ReleaseModelVersionReaderLease",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "reader_lease_id": reader_lease_id,
            },
        )


class TrainingWorkloadClient:
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

    def start_checkpoint_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/StartCheckpointUpload",
            body=_clean(body),
        )

    def finalize_checkpoint_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/FinalizeCheckpointUpload",
            body=_clean(body),
        )

    def fail_checkpoint_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/FailCheckpointUpload",
            body=_clean(body),
        )

    def cancel_checkpoint_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/CancelCheckpointUpload",
            body=_clean(body),
        )

    def upload_to_checkpoint(
        self,
        *,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
        source_path: str,
        validate_uploaded_files: Optional[
            Callable[[list[StorageTransferFile]], None]
        ] = None,
        **upload: Any,
    ) -> UploadResult[dict[str, Any]]:
        start_body = {
            "experiment_id": experiment_id,
            "run_id": run_id,
            "checkpoint_name": checkpoint_name,
            **upload,
        }
        checkpoint = self.start_checkpoint_upload(**start_body)
        if str(checkpoint.get("status", "")).upper() in {"FINALIZED", "READY"}:
            return UploadResult(resource=checkpoint, files=[])

        checkpoint_id = _resource_id(checkpoint, "checkpoint")
        target = self._api.post_dict(
            "/protected/v1/Training/GetRunCheckpointTransferTarget",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_id": checkpoint_id,
                "checkpoint_name": checkpoint_name,
            },
        )
        credential = self._runtime_credential(target)
        finalize_body = {
            key: value
            for key, value in start_body.items()
            if key
            in {
                "experiment_id",
                "run_id",
                "checkpoint_name",
                "execution_id",
                "process_index",
                "process_name",
                "pod_name",
                "idempotency_key",
            }
        }
        finalize_body["checkpoint_id"] = checkpoint_id
        finalize_body["storage_prefix"] = str(target["prefix"])
        try:
            files = upload_path(source_path, credential)
            if validate_uploaded_files is not None:
                validate_uploaded_files(files)
            finalized = self.finalize_checkpoint_upload(
                **finalize_body,
                manifest=_manifest_from_uploaded_files(files, credential["prefix"]),
                file_count=len(files),
                total_size_bytes=sum(file.size_bytes for file in files),
            )
        except Exception as error:
            try:
                self.fail_checkpoint_upload(
                    **finalize_body,
                    failure_reason=type(error).__name__,
                    failure_message=str(error),
                )
            except Exception:
                pass
            raise
        return UploadResult(resource=finalized, files=files)

    def start_run_tokenizer_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/StartRunTokenizerUpload",
            body=_clean(body),
        )

    def finalize_run_tokenizer_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/FinalizeRunTokenizerUpload",
            body=_clean(body),
        )

    def fail_run_tokenizer_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/FailRunTokenizerUpload",
            body=_clean(body),
        )

    def cancel_run_tokenizer_upload(self, **body: Any) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/CancelRunTokenizerUpload",
            body=_clean(body),
        )

    def upload_to_run_tokenizer(
        self,
        *,
        experiment_id: str,
        run_id: str,
        source_path: str,
        **upload: Any,
    ) -> UploadResult[dict[str, Any]]:
        start_body = {
            "experiment_id": experiment_id,
            "run_id": run_id,
            **upload,
        }
        tokenizer = self.start_run_tokenizer_upload(**start_body)
        if str(tokenizer.get("status", "")).upper() in {"FINALIZED", "READY"}:
            return UploadResult(resource=tokenizer, files=[])

        target = self._api.post_dict(
            "/protected/v1/Training/GetRunTokenizerTransferTarget",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )
        credential = self._runtime_credential(target)
        try:
            files = upload_path(source_path, credential)
            finalized = self.finalize_run_tokenizer_upload(
                experiment_id=experiment_id,
                run_id=run_id,
                manifest=_manifest_from_uploaded_files(files, credential["prefix"]),
                file_count=len(files),
                total_size_bytes=sum(file.size_bytes for file in files),
            )
        except Exception as error:
            try:
                self.fail_run_tokenizer_upload(
                    experiment_id=experiment_id,
                    run_id=run_id,
                    failure_reason=type(error).__name__,
                    failure_message=str(error),
                )
            except Exception:
                pass
            raise
        return UploadResult(resource=finalized, files=files)

    def _runtime_credential(self, target: dict[str, Any]) -> dict[str, Any]:
        if self._cas_client_factory is None:
            raise RuntimeError("CAS client is required for workload storage transfer")
        return create_runtime_s3_credential(
            cas_client_factory=self._cas_client_factory,
            role_name=self._s3_role_name,
            endpoint_url=self._s3_endpoint_url,
            bucket=str(target["bucket"]),
            prefix=str(target["prefix"]),
            retry_policy=self._api.retry_policy,
        )

    def acquire_checkpoint_reader_lease(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_id: Optional[str] = None,
        checkpoint_name: Optional[str] = None,
        execution_id: Optional[str] = None,
        owner_resource_type: str = "training_run",
        owner_resource_id: Optional[str] = None,
        owner_process_id: Optional[str] = None,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/AcquireRunCheckpointReaderLease",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_name": checkpoint_name,
                    "execution_id": execution_id,
                    "owner_resource_type": owner_resource_type,
                    "owner_resource_id": owner_resource_id,
                    "owner_process_id": owner_process_id,
                    "lease_ttl_seconds": lease_ttl_seconds,
                }
            ),
        )

    def heartbeat_checkpoint_reader_lease(
        self,
        reader_lease_id: str,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/HeartbeatRunCheckpointReaderLease",
            body={
                "reader_lease_id": reader_lease_id,
                "lease_ttl_seconds": lease_ttl_seconds,
            },
        )

    def release_checkpoint_reader_lease(self, reader_lease_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/ReleaseRunCheckpointReaderLease",
            body={"reader_lease_id": reader_lease_id},
        )

    def acquire_run_tokenizer_reader_lease(
        self,
        experiment_id: str,
        run_id: str,
        owner_resource_type: str,
        owner_resource_id: str,
        owner_process_id: Optional[str] = None,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/AcquireRunTokenizerReaderLease",
            body=_clean(
                {
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "owner_resource_type": owner_resource_type,
                    "owner_resource_id": owner_resource_id,
                    "owner_process_id": owner_process_id,
                    "lease_ttl_seconds": lease_ttl_seconds,
                }
            ),
        )

    def heartbeat_run_tokenizer_reader_lease(
        self,
        experiment_id: str,
        run_id: str,
        reader_lease_id: str,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/HeartbeatRunTokenizerReaderLease",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "reader_lease_id": reader_lease_id,
                "lease_ttl_seconds": lease_ttl_seconds,
            },
        )

    def release_run_tokenizer_reader_lease(
        self,
        experiment_id: str,
        run_id: str,
        reader_lease_id: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/workload/v1/Training/ReleaseRunTokenizerReaderLease",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "reader_lease_id": reader_lease_id,
            },
        )


class InternalWorkloadClient:
    def __init__(
        self,
        api: APIClient,
        *,
        cas_client_factory: Callable[[], Any] | None = None,
        s3_endpoint_url: str = S3_ENDPOINT_URL,
        s3_role_name: str = CAS_S3_ROLE_NAME,
    ):
        self.data_hub = DataHubWorkloadClient(api)
        self.model_registry = ModelRegistryWorkloadClient(
            api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=s3_endpoint_url,
            s3_role_name=s3_role_name,
        )
        self.training = TrainingWorkloadClient(
            api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=s3_endpoint_url,
            s3_role_name=s3_role_name,
        )

    @classmethod
    def from_client(cls, client: Any) -> "InternalWorkloadClient":
        return cls(
            client._api,
            cas_client_factory=client.create_cas_client,
            s3_endpoint_url=client.s3_endpoint_url,
            s3_role_name=client.s3_role_name,
        )


def _resource_id(resource: dict[str, Any], kind: str) -> str:
    value = (
        resource.get(f"{kind}_id") or resource.get("resource_id") or resource.get("id")
    )
    if not value:
        raise RuntimeError(f"{kind} upload response did not contain a resource ID")
    return str(value)


def _manifest_from_uploaded_files(
    files: Iterable[StorageTransferFile],
    prefix: str,
) -> dict[str, Any]:
    normalized_prefix = str(prefix or "").strip("/")
    folder = f"{normalized_prefix}/" if normalized_prefix else ""
    return {
        "files": [
            {
                "path": (
                    file.object_key[len(folder) :]
                    if folder and file.object_key.startswith(folder)
                    else file.object_key
                ),
                "size": int(file.size_bytes),
            }
            for file in files
        ]
    }

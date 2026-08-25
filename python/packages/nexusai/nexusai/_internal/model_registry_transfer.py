from collections.abc import Callable, Iterable
from typing import Any, Optional

from .cas_storage import create_runtime_s3_credential
from ..config import CAS_S3_ROLE_NAME, DEFAULT_EXPIRES_IN, S3_ENDPOINT_URL
from .http import APIClient
from .results import (
    InternalDownloadResult as DownloadResult,
    InternalUploadResult as UploadResult,
)
from .serving_manifest import build_serving_manifest
from .storage import download_prefix, upload_path


def _clean(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


class ModelRegistryTransferClient:
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

    def create_model(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/CreateModel",
            body={
                "name": name,
                "extras_data": extras_data,
            },
        )

    def list_models(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/ModelRegistry/ListModels",
            body={
                "page": page,
                "limit": limit,
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

    def get_model(self, model_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/GetModel",
            body={
                "model_id": model_id,
            },
        )

    def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        latest_version_id: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/UpdateModel",
            body={
                "model_id": model_id,
                "name": name,
                "latest_version_id": latest_version_id,
                "extras_data": extras_data,
            },
        )

    def get_model_by_name(self, name: str) -> Optional[dict[str, Any]]:
        models = self.list_models(name=name)
        return next((model for model in models if model.get("name") == name), None)

    def get_or_create_model(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        existing = self.get_model_by_name(name)
        if existing:
            return existing
        return self.create_model(name=name, extras_data=extras_data)

    def delete_model(self, model_id: str) -> None:
        self._api.post(
            "/v1/ModelRegistry/DeleteModel",
            body={
                "model_id": model_id,
            },
        )

    def create_model_version(
        self,
        model_id: str,
        name: str,
        training_experiment_name: Optional[str] = None,
        training_run_name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/CreateModelVersion",
            body={
                "model_id": model_id,
                "name": name,
                "training_experiment_name": training_experiment_name,
                "training_run_name": training_run_name,
                "extras_data": extras_data,
            },
        )

    def create_model_version_from_checkpoint(
        self,
        model_id: str,
        name: str,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/CreateModelVersionFromCheckpoint",
            body={
                "model_id": model_id,
                "name": name,
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
                "extras_data": extras_data,
            },
        )

    def list_model_versions(
        self,
        model_id: str,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        training_experiment_name: Optional[str] = None,
        training_run_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/ModelRegistry/ListModelVersions",
            body={
                "model_id": model_id,
                "page": page,
                "limit": limit,
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
                "training_experiment_name": training_experiment_name,
                "training_run_name": training_run_name,
            },
        )

    def get_model_version(
        self,
        model_id: str,
        model_version_id: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/GetModelVersion",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
            },
        )

    def update_model_version(
        self,
        model_id: str,
        model_version_id: str,
        name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/UpdateModelVersion",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "name": name,
                "extras_data": extras_data,
            },
        )

    def list_model_version_files(
        self,
        model_id: str,
        model_version_id: str,
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/ModelRegistry/ListModelVersionFiles",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
            },
        )

    def get_model_version_size(
        self,
        model_id: str,
        model_version_id: str,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/GetModelVersionSize",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
            },
        )

    def delete_model_version(self, model_id: str, model_version_id: str) -> None:
        self._api.post(
            "/v1/ModelRegistry/DeleteModelVersion",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
            },
        )

    def finalize_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        manifest: Optional[dict[str, Any]] = None,
        file_count: int = 0,
        total_size_bytes: int = 0,
        artifact_format: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/FinalizeModelVersionUpload",
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

    def start_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        idempotency_key: Optional[str] = None,
        declared_manifest: Optional[dict[str, Any]] = None,
        reserved_quota_bytes: int = 0,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model_id": model_id,
            "model_version_id": model_version_id,
            "idempotency_key": idempotency_key,
            "declared_manifest": declared_manifest,
        }
        if reserved_quota_bytes:
            body["reserved_quota_bytes"] = reserved_quota_bytes
        return self._api.post_dict(
            "/v1/ModelRegistry/StartModelVersionUpload",
            body=_clean(body),
        )

    def fail_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/FailModelVersionUpload",
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
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/ModelRegistry/CancelModelVersionUpload",
            body=_clean(
                {
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "failure_reason": failure_reason,
                    "failure_message": failure_message,
                }
            ),
        )

    def upload_model_version(
        self,
        model_name: str,
        version_name: str,
        source_path: str,
        model_extras_data: Optional[dict[str, Any]] = None,
        version_extras_data: Optional[dict[str, Any]] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
        artifact_format: Optional[str] = None,
        model_architecture: Optional[str] = None,
        runtime: str = "sglang",
        accelerators: Iterable[str] = ("amd",),
    ) -> UploadResult[dict[str, Any]]:
        model = self.get_or_create_model(
            name=model_name,
            extras_data=model_extras_data,
        )
        model_version = self.create_model_version(
            model_id=model["id"],
            name=version_name,
            extras_data=version_extras_data,
        )
        return self._upload_to_model_version_resource(
            model_id=model["id"],
            model_version_id=model_version["id"],
            source_path=source_path,
            model_version=model_version,
            artifact_format=artifact_format,
            model_architecture=model_architecture,
            runtime=runtime,
            accelerators=accelerators,
        )

    def upload_model_version_by_id(
        self,
        model_id: str,
        version_name: str,
        source_path: str,
        version_extras_data: Optional[dict[str, Any]] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
        artifact_format: Optional[str] = None,
        model_architecture: Optional[str] = None,
        runtime: str = "sglang",
        accelerators: Iterable[str] = ("amd",),
    ) -> UploadResult[dict[str, Any]]:
        model_version = self.create_model_version(
            model_id=model_id,
            name=version_name,
            extras_data=version_extras_data,
        )
        return self._upload_to_model_version_resource(
            model_id=model_id,
            model_version_id=model_version["id"],
            source_path=source_path,
            model_version=model_version,
            artifact_format=artifact_format,
            model_architecture=model_architecture,
            runtime=runtime,
            accelerators=accelerators,
        )

    def upload_to_model_version(
        self,
        model_id: str,
        model_version_id: str,
        source_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
        artifact_format: Optional[str] = None,
        model_architecture: Optional[str] = None,
        runtime: str = "sglang",
        accelerators: Iterable[str] = ("amd",),
    ) -> UploadResult[dict[str, Any]]:
        model_version = self.get_model_version(
            model_id=model_id,
            model_version_id=model_version_id,
        )
        return self._upload_to_model_version_resource(
            model_id=model_id,
            model_version_id=model_version_id,
            source_path=source_path,
            model_version=model_version,
            artifact_format=artifact_format,
            model_architecture=model_architecture,
            runtime=runtime,
            accelerators=accelerators,
        )

    def _upload_to_model_version_resource(
        self,
        *,
        model_id: str,
        model_version_id: str,
        source_path: str,
        model_version: dict[str, Any],
        artifact_format: Optional[str] = None,
        model_architecture: Optional[str] = None,
        runtime: str = "sglang",
        accelerators: Iterable[str] = ("amd",),
    ) -> UploadResult[dict[str, Any]]:
        self.start_model_version_upload(
            model_id=model_id,
            model_version_id=model_version_id,
        )
        credential = self._create_model_version_runtime_credential(
            model_id=model_id,
            model_version_id=model_version_id,
            model_version=model_version,
        )
        try:
            files = upload_path(source_path, credential)
            finalized_model_version = self.finalize_model_version_upload(
                model_id=model_id,
                model_version_id=model_version_id,
                manifest=build_serving_manifest(
                    files,
                    storage_prefix=credential["prefix"],
                    model_version_id=model_version_id,
                    artifact_format=artifact_format,
                    model_architecture=model_architecture,
                    runtime=runtime,
                    accelerators=accelerators,
                ),
                file_count=len(files),
                total_size_bytes=sum(int(file.size_bytes) for file in files),
                artifact_format=artifact_format,
            )
        except Exception as exc:
            try:
                self.fail_model_version_upload(
                    model_id=model_id,
                    model_version_id=model_version_id,
                    failure_reason=type(exc).__name__,
                    failure_message=str(exc),
                )
            finally:
                raise
        return UploadResult(
            resource=finalized_model_version,
            files=files,
        )

    def download_model(
        self,
        model_id: str,
        destination_path: str,
        model_version_id: Optional[str] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> DownloadResult[dict[str, Any]]:
        model = self.get_model(model_id)
        latest_version = model.get("latest_version")
        version_id = model_version_id or (
            latest_version.get("id") if latest_version is not None else None
        )
        if not version_id:
            raise ValueError(
                "model_version_id is required when model has no latest version"
            )
        model_version = self.get_model_version(
            model_id=model_id,
            model_version_id=version_id,
        )
        credential = self._create_model_version_runtime_credential(
            model_id=model_id,
            model_version_id=version_id,
            model_version=model_version,
        )
        files = download_prefix(destination_path, credential)
        return DownloadResult(
            resource=model_version,
            files=files,
        )

    def download_model_version(
        self,
        model_id: str,
        model_version_id: str,
        destination_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> DownloadResult[dict[str, Any]]:
        return self.download_model(
            model_id=model_id,
            model_version_id=model_version_id,
            destination_path=destination_path,
            expires_in=expires_in,
        )

    def _create_model_version_runtime_credential(
        self,
        *,
        model_id: str,
        model_version_id: str,
        model_version: dict[str, Any],
    ) -> dict[str, Any]:
        target = self._api.post_dict(
            "/protected/v1/ModelRegistry/GetModelVersionTransferTarget",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
            },
        )
        return create_runtime_s3_credential(
            cas_client_factory=self._cas_client_factory,
            role_name=self._s3_role_name,
            endpoint_url=self._s3_endpoint_url,
            bucket=str(target["bucket"]),
            prefix=str(target["prefix"]),
            retry_policy=self._api.retry_policy,
        )

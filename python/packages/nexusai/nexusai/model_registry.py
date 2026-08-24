from collections.abc import Callable
from typing import Any, Optional

from ._internal.model_registry_transfer import ModelRegistryTransferClient
from ._internal.http import APIClient
from ._internal.results import to_public_transfer_files
from .config import CAS_S3_ROLE_NAME, DEFAULT_EXPIRES_IN, S3_ENDPOINT_URL
from .models import (
    ActionResult,
    FileItem,
    ModelDetail,
    ModelSummary,
    ModelVersionDetail,
    ModelVersionSizeResult,
    ModelVersionSummary,
    Page,
)
from .results import DownloadResult, UploadResult


class ModelRegistryClient:
    def __init__(
        self,
        api: APIClient,
        *,
        cas_client_factory: Callable[[], Any] | None = None,
        s3_endpoint_url: str = S3_ENDPOINT_URL,
        s3_role_name: str = CAS_S3_ROLE_NAME,
    ) -> None:
        self._api = api
        self._transfer = ModelRegistryTransferClient(
            api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=s3_endpoint_url,
            s3_role_name=s3_role_name,
        )

    def create_model(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ModelDetail:
        return self._api.post_model(
            "/v1/ModelRegistry/CreateModel",
            ModelDetail,
            body={"name": name, "extras_data": extras_data},
        )

    def list_models(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[ModelSummary]:
        return self._api.post_page(
            "/v1/ModelRegistry/ListModels",
            ModelSummary,
            body={
                "page": page,
                "limit": limit,
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

    def get_model(self, model_id: str) -> ModelDetail:
        return self._api.post_model(
            "/v1/ModelRegistry/GetModel",
            ModelDetail,
            body={"model_id": model_id},
        )

    def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        latest_version_id: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ModelDetail:
        return self._api.post_model(
            "/v1/ModelRegistry/UpdateModel",
            ModelDetail,
            body={
                "model_id": model_id,
                "name": name,
                "latest_version_id": latest_version_id,
                "extras_data": extras_data,
            },
        )

    def get_model_by_name(self, name: str) -> Optional[ModelSummary]:
        return next(
            (model for model in self.list_models(name=name) if model.name == name),
            None,
        )

    def get_or_create_model(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ModelSummary | ModelDetail:
        return self.get_model_by_name(name) or self.create_model(name, extras_data)

    def delete_model(self, model_id: str) -> Optional[ActionResult]:
        return self._api.post_optional_model(
            "/v1/ModelRegistry/DeleteModel",
            ActionResult,
            body={"model_id": model_id},
        )

    def create_model_version(
        self,
        model_id: str,
        name: str,
        training_experiment_name: Optional[str] = None,
        training_run_name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ModelVersionDetail:
        return self._api.post_model(
            "/v1/ModelRegistry/CreateModelVersion",
            ModelVersionDetail,
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
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/ModelRegistry/CreateModelVersionFromCheckpoint",
            ActionResult,
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
    ) -> Page[ModelVersionSummary]:
        return self._api.post_page(
            "/v1/ModelRegistry/ListModelVersions",
            ModelVersionSummary,
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
    ) -> ModelVersionDetail:
        return self._api.post_model(
            "/v1/ModelRegistry/GetModelVersion",
            ModelVersionDetail,
            body={"model_id": model_id, "model_version_id": model_version_id},
        )

    def update_model_version(
        self,
        model_id: str,
        model_version_id: str,
        name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> ModelVersionDetail:
        return self._api.post_model(
            "/v1/ModelRegistry/UpdateModelVersion",
            ModelVersionDetail,
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
    ) -> list[FileItem]:
        return [
            FileItem.from_dict(item)
            for item in self._api.post_list(
                "/v1/ModelRegistry/ListModelVersionFiles",
                body={
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                },
            )
        ]

    def get_model_version_size(
        self,
        model_id: str,
        model_version_id: str,
    ) -> ModelVersionSizeResult:
        return self._api.post_model(
            "/v1/ModelRegistry/GetModelVersionSize",
            ModelVersionSizeResult,
            body={"model_id": model_id, "model_version_id": model_version_id},
        )

    def delete_model_version(
        self,
        model_id: str,
        model_version_id: str,
    ) -> Optional[ActionResult]:
        return self._api.post_optional_model(
            "/v1/ModelRegistry/DeleteModelVersion",
            ActionResult,
            body={"model_id": model_id, "model_version_id": model_version_id},
        )

    def start_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        idempotency_key: Optional[str] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/ModelRegistry/StartModelVersionUpload",
            ActionResult,
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "idempotency_key": idempotency_key,
            },
        )

    def finalize_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        artifact_format: Optional[str] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/ModelRegistry/FinalizeModelVersionUpload",
            ActionResult,
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "artifact_format": artifact_format,
            },
        )

    def fail_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/ModelRegistry/FailModelVersionUpload",
            ActionResult,
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "failure_reason": failure_reason,
                "failure_message": failure_message,
            },
        )

    def cancel_model_version_upload(
        self,
        model_id: str,
        model_version_id: str,
        failure_reason: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/ModelRegistry/CancelModelVersionUpload",
            ActionResult,
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "failure_reason": failure_reason,
                "failure_message": failure_message,
            },
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
    ) -> UploadResult[ModelVersionDetail]:
        result = self._transfer.upload_model_version(
            model_name=model_name,
            version_name=version_name,
            source_path=source_path,
            model_extras_data=model_extras_data,
            version_extras_data=version_extras_data,
            expires_in=expires_in,
            artifact_format=artifact_format,
        )
        model = self.get_model_by_name(model_name)
        if model is None:
            raise RuntimeError(f"Uploaded model {model_name!r} could not be resolved")
        version_id = str(
            result.resource.get("resource_id") or result.resource.get("id") or ""
        )
        if not version_id:
            raise RuntimeError("Upload response did not contain a model version ID")
        return UploadResult(
            resource=self.get_model_version(model.id, version_id),
            files=to_public_transfer_files(result.files),
        )

    def upload_model_version_by_id(
        self,
        model_id: str,
        version_name: str,
        source_path: str,
        version_extras_data: Optional[dict[str, Any]] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
        artifact_format: Optional[str] = None,
    ) -> UploadResult[ModelVersionDetail]:
        result = self._transfer.upload_model_version_by_id(
            model_id=model_id,
            version_name=version_name,
            source_path=source_path,
            version_extras_data=version_extras_data,
            expires_in=expires_in,
            artifact_format=artifact_format,
        )
        version_id = str(
            result.resource.get("resource_id") or result.resource.get("id") or ""
        )
        if not version_id:
            raise RuntimeError("Upload response did not contain a model version ID")
        return UploadResult(
            resource=self.get_model_version(model_id, version_id),
            files=to_public_transfer_files(result.files),
        )

    def upload_to_model_version(
        self,
        model_id: str,
        model_version_id: str,
        source_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
        artifact_format: Optional[str] = None,
    ) -> UploadResult[ModelVersionDetail]:
        result = self._transfer.upload_to_model_version(
            model_id=model_id,
            model_version_id=model_version_id,
            source_path=source_path,
            expires_in=expires_in,
            artifact_format=artifact_format,
        )
        return UploadResult(
            resource=self.get_model_version(model_id, model_version_id),
            files=to_public_transfer_files(result.files),
        )

    def download_model(
        self,
        model_id: str,
        destination_path: str,
        model_version_id: Optional[str] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> DownloadResult[ModelVersionDetail]:
        result = self._transfer.download_model(
            model_id=model_id,
            destination_path=destination_path,
            model_version_id=model_version_id,
            expires_in=expires_in,
        )
        return DownloadResult(
            resource=ModelVersionDetail.from_dict(result.resource),
            files=to_public_transfer_files(result.files),
        )

    def download_model_version(
        self,
        model_id: str,
        model_version_id: str,
        destination_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> DownloadResult[ModelVersionDetail]:
        result = self._transfer.download_model_version(
            model_id=model_id,
            model_version_id=model_version_id,
            destination_path=destination_path,
            expires_in=expires_in,
        )
        return DownloadResult(
            resource=ModelVersionDetail.from_dict(result.resource),
            files=to_public_transfer_files(result.files),
        )

from typing import Any, Optional

from .config import DEFAULT_EXPIRES_IN
from .http import APIClient
from .results import DownloadResult, UploadResult
from .storage import download_prefix, upload_path


class RpcModelRegistryClient:
    def __init__(self, api: APIClient):
        self._api = api

    def create_model(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        status: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/ModelRegistry/UpdateModelVersion",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "name": name,
                "status": status,
                "extras_data": extras_data,
            },
        )

    def list_model_version_files(
        self,
        model_id: str,
        model_version_id: str,
    ) -> list[dict[str, Any]]:
        return self._api.post(
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
        return self._api.post(
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

    def create_upload_credential(
        self,
        model_id: str,
        model_version_id: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/ModelRegistry/UploadModelVersion",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "expires_in": expires_in,
            },
        )

    def create_download_credential(
        self,
        model_id: str,
        model_version_id: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/ModelRegistry/DownloadModelVersion",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "expires_in": expires_in,
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
    ) -> UploadResult:
        model = self.get_or_create_model(
            name=model_name,
            extras_data=model_extras_data,
        )
        model_version = self.create_model_version(
            model_id=model["id"],
            name=version_name,
            extras_data=version_extras_data,
        )
        credential = self.create_upload_credential(
            model_id=model["id"],
            model_version_id=model_version["id"],
            expires_in=expires_in,
        )
        files = upload_path(source_path, credential)
        return UploadResult(resource=model_version, credential=credential, files=files)

    def upload_model_version_by_id(
        self,
        model_id: str,
        version_name: str,
        source_path: str,
        version_extras_data: Optional[dict[str, Any]] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> UploadResult:
        model_version = self.create_model_version(
            model_id=model_id,
            name=version_name,
            extras_data=version_extras_data,
        )
        credential = self.create_upload_credential(
            model_id=model_id,
            model_version_id=model_version["id"],
            expires_in=expires_in,
        )
        files = upload_path(source_path, credential)
        return UploadResult(resource=model_version, credential=credential, files=files)

    def upload_to_model_version(
        self,
        model_id: str,
        model_version_id: str,
        source_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> UploadResult:
        model_version = self.get_model_version(
            model_id=model_id,
            model_version_id=model_version_id,
        )
        credential = self.create_upload_credential(
            model_id=model_id,
            model_version_id=model_version_id,
            expires_in=expires_in,
        )
        files = upload_path(source_path, credential)
        return UploadResult(resource=model_version, credential=credential, files=files)

    def download_model(
        self,
        model_id: str,
        destination_path: str,
        model_version_id: Optional[str] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> DownloadResult:
        model = self.get_model(model_id)
        version_id = model_version_id or model.get("latest_version_id")
        if not version_id:
            raise ValueError(
                "model_version_id is required when model has no latest version"
            )
        model_version = self.get_model_version(
            model_id=model_id,
            model_version_id=version_id,
        )
        credential = self.create_download_credential(
            model_id=model_id,
            model_version_id=version_id,
            expires_in=expires_in,
        )
        files = download_prefix(destination_path, credential)
        return DownloadResult(
            resource=model_version,
            credential=credential,
            files=files,
        )

    def download_model_version(
        self,
        model_id: str,
        model_version_id: str,
        destination_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> DownloadResult:
        return self.download_model(
            model_id=model_id,
            model_version_id=model_version_id,
            destination_path=destination_path,
            expires_in=expires_in,
        )

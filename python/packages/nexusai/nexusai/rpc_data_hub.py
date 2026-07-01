from typing import Any, Optional

from .config import DEFAULT_EXPIRES_IN
from .http import APIClient
from .results import DownloadResult, UploadResult
from .storage import download_prefix, upload_path


class RpcDataHubClient:
    def __init__(self, api: APIClient):
        self._api = api

    def create_dataset(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/DataHub/CreateDataset",
            body={
                "name": name,
                "extras_data": extras_data,
            },
        )

    def list_datasets(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post(
            "/v1/DataHub/ListDatasets",
            body={
                "page": page,
                "limit": limit,
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/DataHub/GetDataset",
            body={
                "dataset_id": dataset_id,
            },
        )

    def update_dataset(
        self,
        dataset_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/DataHub/UpdateDataset",
            body={
                "dataset_id": dataset_id,
                "name": name,
                "status": status,
                "extras_data": extras_data,
            },
        )

    def delete_dataset(self, dataset_id: str) -> None:
        self._api.post(
            "/v1/DataHub/DeleteDataset",
            body={
                "dataset_id": dataset_id,
            },
        )

    def list_dataset_files(self, dataset_id: str) -> list[dict[str, Any]]:
        return self._api.post(
            "/v1/DataHub/ListDatasetFiles",
            body={
                "dataset_id": dataset_id,
            },
        )

    def get_dataset_size(self, dataset_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/DataHub/GetDatasetSize",
            body={
                "dataset_id": dataset_id,
            },
        )

    def upload_dataset_instruction(self, dataset_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/DataHub/UploadDatasetInstruction",
            body={
                "dataset_id": dataset_id,
            },
        )

    def create_upload_credential(
        self,
        dataset_id: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/DataHub/UploadDataset",
            body={
                "dataset_id": dataset_id,
                "expires_in": expires_in,
            },
        )

    def create_download_credential(
        self,
        dataset_id: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/DataHub/DownloadDataset",
            body={
                "dataset_id": dataset_id,
                "expires_in": expires_in,
            },
        )

    def upload_dataset(
        self,
        name: str,
        source_path: str,
        extras_data: Optional[dict[str, Any]] = None,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> UploadResult:
        dataset = self.create_dataset(name=name, extras_data=extras_data)
        credential = self.create_upload_credential(
            dataset_id=dataset["id"],
            expires_in=expires_in,
        )
        files = upload_path(source_path, credential)
        return UploadResult(resource=dataset, credential=credential, files=files)

    def upload_to_dataset(
        self,
        dataset_id: str,
        source_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> UploadResult:
        dataset = self.get_dataset(dataset_id)
        credential = self.create_upload_credential(
            dataset_id=dataset_id,
            expires_in=expires_in,
        )
        files = upload_path(source_path, credential)
        return UploadResult(resource=dataset, credential=credential, files=files)

    def download_dataset(
        self,
        dataset_id: str,
        destination_path: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> DownloadResult:
        dataset = self.get_dataset(dataset_id)
        credential = self.create_download_credential(
            dataset_id=dataset_id,
            expires_in=expires_in,
        )
        files = download_prefix(destination_path, credential)
        return DownloadResult(resource=dataset, credential=credential, files=files)

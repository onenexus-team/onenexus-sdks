from collections.abc import Callable
from typing import Any, Optional

from ._internal.data_hub_transfer import DataHubTransferClient
from ._internal.http import APIClient
from ._internal.results import to_public_transfer_files
from .config import CAS_S3_ROLE_NAME, S3_ENDPOINT_URL
from .models import (
    ActionResult,
    DatasetDetail,
    DatasetSizeResult,
    DatasetSummary,
    FileItem,
    Page,
    UploadInstruction,
)
from .results import DownloadResult, UploadResult


class DataHubClient:
    def __init__(
        self,
        api: APIClient,
        *,
        cas_client_factory: Callable[[], Any] | None = None,
        s3_endpoint_url: str = S3_ENDPOINT_URL,
        s3_role_name: str = CAS_S3_ROLE_NAME,
    ) -> None:
        self._api = api
        self._transfer = DataHubTransferClient(
            api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=s3_endpoint_url,
            s3_role_name=s3_role_name,
        )

    def create_dataset(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> DatasetDetail:
        return self._api.post_model(
            "/v1/DataHub/CreateDataset",
            DatasetDetail,
            body={"name": name, "extras_data": extras_data},
        )

    def list_datasets(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[DatasetSummary]:
        return self._api.post_page(
            "/v1/DataHub/ListDatasets",
            DatasetSummary,
            body={
                "page": page,
                "limit": limit,
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

    def get_dataset(self, dataset_id: str) -> DatasetDetail:
        return self._api.post_model(
            "/v1/DataHub/GetDataset",
            DatasetDetail,
            body={"dataset_id": dataset_id},
        )

    def update_dataset(
        self,
        dataset_id: str,
        name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> DatasetDetail:
        return self._api.post_model(
            "/v1/DataHub/UpdateDataset",
            DatasetDetail,
            body={
                "dataset_id": dataset_id,
                "name": name,
                "extras_data": extras_data,
            },
        )

    def delete_dataset(self, dataset_id: str) -> ActionResult:
        return self._api.post_model(
            "/v1/DataHub/DeleteDataset",
            ActionResult,
            body={"dataset_id": dataset_id},
        )

    def start_dataset_upload(
        self,
        dataset_id: str,
        idempotency_key: Optional[str] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/DataHub/StartDatasetUpload",
            ActionResult,
            body={
                "dataset_id": dataset_id,
                "idempotency_key": idempotency_key,
            },
        )

    def finalize_dataset_upload(
        self,
        dataset_id: str,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/DataHub/FinalizeDatasetUpload",
            ActionResult,
            body={"dataset_id": dataset_id},
        )

    def fail_dataset_upload(
        self,
        dataset_id: str,
        failure_reason: str,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/DataHub/FailDatasetUpload",
            ActionResult,
            body={
                "dataset_id": dataset_id,
                "failure_reason": failure_reason,
            },
        )

    def cancel_dataset_upload(
        self,
        dataset_id: str,
        cancel_reason: Optional[str] = None,
    ) -> ActionResult:
        return self._api.post_model(
            "/v1/DataHub/CancelDatasetUpload",
            ActionResult,
            body={"dataset_id": dataset_id, "cancel_reason": cancel_reason},
        )

    def list_dataset_files(self, dataset_id: str) -> list[FileItem]:
        return [
            FileItem.from_dict(item)
            for item in self._api.post_list(
                "/v1/DataHub/ListDatasetFiles",
                body={"dataset_id": dataset_id},
            )
        ]

    def get_dataset_size(self, dataset_id: str) -> DatasetSizeResult:
        return self._api.post_model(
            "/v1/DataHub/GetDatasetSize",
            DatasetSizeResult,
            body={"dataset_id": dataset_id},
        )

    def upload_dataset_instruction(self, dataset_id: str) -> UploadInstruction:
        return self._api.post_model(
            "/v1/DataHub/GetUploadDatasetInstruction",
            UploadInstruction,
            body={"dataset_id": dataset_id},
        )

    get_upload_dataset_instruction = upload_dataset_instruction

    def upload_dataset(
        self,
        name: str,
        source_path: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> UploadResult[DatasetDetail]:
        result = self._transfer.upload_dataset(name, source_path, extras_data)
        return UploadResult(
            resource=DatasetDetail.from_dict(result.resource),
            files=to_public_transfer_files(result.files),
        )

    def upload_to_dataset(
        self,
        dataset_id: str,
        source_path: str,
    ) -> UploadResult[DatasetDetail]:
        result = self._transfer.upload_to_dataset(dataset_id, source_path)
        return UploadResult(
            resource=DatasetDetail.from_dict(result.resource),
            files=to_public_transfer_files(result.files),
        )

    def download_dataset(
        self,
        dataset_id: str,
        destination_path: str,
    ) -> DownloadResult[DatasetDetail]:
        result = self._transfer.download_dataset(dataset_id, destination_path)
        return DownloadResult(
            resource=DatasetDetail.from_dict(result.resource),
            files=to_public_transfer_files(result.files),
        )

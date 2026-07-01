from collections.abc import Callable, Iterable
from typing import Any, Optional

from .cas_storage import create_runtime_s3_credential
from .config import CAS_S3_ROLE_NAME, S3_ENDPOINT_URL
from .http import APIClient
from .results import DownloadResult, UploadResult
from .storage import StorageTransferFile, download_prefix, upload_path


class RpcDataHubClient:
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

    def create_dataset(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
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
        return self._api.post_list(
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
        return self._api.post_dict(
            "/v1/DataHub/GetDataset",
            body={
                "dataset_id": dataset_id,
            },
        )

    def update_dataset(
        self,
        dataset_id: str,
        name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/UpdateDataset",
            body={
                "dataset_id": dataset_id,
                "name": name,
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

    def start_dataset_upload(
        self,
        dataset_id: str,
        idempotency_key: Optional[str] = None,
        declared_manifest: Optional[dict[str, Any]] = None,
        reserved_quota_bytes: int = 0,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/StartDatasetUpload",
            body={
                "dataset_id": dataset_id,
                "idempotency_key": idempotency_key,
                "declared_manifest": declared_manifest,
                "reserved_quota_bytes": reserved_quota_bytes,
                "lease_ttl_seconds": lease_ttl_seconds,
            },
        )

    def finalize_dataset_upload(
        self,
        dataset_id: str,
        manifest: Optional[dict[str, Any]] = None,
        file_count: int = 0,
        total_size_bytes: int = 0,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/FinalizeDatasetUpload",
            body={
                "dataset_id": dataset_id,
                "manifest": manifest,
                "file_count": file_count,
                "total_size_bytes": total_size_bytes,
            },
        )

    def fail_dataset_upload(
        self,
        dataset_id: str,
        failure_reason: str,
        last_error: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/FailDatasetUpload",
            body={
                "dataset_id": dataset_id,
                "failure_reason": failure_reason,
                "last_error": last_error,
            },
        )

    def cancel_dataset_upload(
        self,
        dataset_id: str,
        cancel_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/CancelDatasetUpload",
            body={
                "dataset_id": dataset_id,
                "cancel_reason": cancel_reason,
            },
        )

    def list_dataset_files(self, dataset_id: str) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/DataHub/ListDatasetFiles",
            body={
                "dataset_id": dataset_id,
            },
        )

    def get_dataset_size(self, dataset_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/GetDatasetSize",
            body={
                "dataset_id": dataset_id,
            },
        )

    def upload_dataset_instruction(self, dataset_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/GetUploadDatasetInstruction",
            body={
                "dataset_id": dataset_id,
            },
        )

    get_upload_dataset_instruction = upload_dataset_instruction

    def upload_dataset(
        self,
        name: str,
        source_path: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> UploadResult:
        dataset = self.create_dataset(name=name, extras_data=extras_data)
        self.start_dataset_upload(dataset_id=dataset["id"])
        credential = self._create_dataset_runtime_credential(dataset_id=dataset["id"])
        try:
            files = upload_path(source_path, credential)
            self.finalize_dataset_upload(
                dataset_id=dataset["id"],
                manifest=_manifest_from_uploaded_files(
                    files, prefix=credential["prefix"]
                ),
                file_count=len(files),
                total_size_bytes=sum(int(file.size_bytes) for file in files),
            )
        except Exception as error:
            self._fail_dataset_upload_best_effort(dataset["id"], error)
            raise
        return UploadResult(
            resource=self.get_dataset(dataset["id"]),
            files=files,
        )

    def upload_to_dataset(
        self,
        dataset_id: str,
        source_path: str,
    ) -> UploadResult:
        self.get_dataset(dataset_id)
        self.start_dataset_upload(dataset_id=dataset_id)
        credential = self._create_dataset_runtime_credential(dataset_id=dataset_id)
        try:
            files = upload_path(source_path, credential)
            self.finalize_dataset_upload(
                dataset_id=dataset_id,
                manifest=_manifest_from_uploaded_files(
                    files, prefix=credential["prefix"]
                ),
                file_count=len(files),
                total_size_bytes=sum(int(file.size_bytes) for file in files),
            )
        except Exception as error:
            self._fail_dataset_upload_best_effort(dataset_id, error)
            raise
        return UploadResult(
            resource=self.get_dataset(dataset_id),
            files=files,
        )

    def _fail_dataset_upload_best_effort(self, dataset_id: str, error: Exception) -> None:
        try:
            self.fail_dataset_upload(
                dataset_id=dataset_id,
                failure_reason=type(error).__name__,
                last_error=str(error),
            )
        except Exception:
            pass

    def download_dataset(
        self,
        dataset_id: str,
        destination_path: str,
    ) -> DownloadResult:
        dataset = self.get_dataset(dataset_id)
        credential = self._create_dataset_runtime_credential(dataset_id=dataset_id)
        files = download_prefix(destination_path, credential)
        return DownloadResult(resource=dataset, files=files)

    def _create_dataset_runtime_credential(self, dataset_id: str) -> dict[str, Any]:
        workspace = self._resolve_tenant_workspace()
        return create_runtime_s3_credential(
            cas_client_factory=self._cas_client_factory,
            role_name=self._s3_role_name,
            endpoint_url=self._s3_endpoint_url,
            bucket=workspace["datahub_bucket"],
            prefix=str(dataset_id),
        )

    def _resolve_tenant_workspace(self) -> dict[str, Any]:
        response = self._api.post(
            "/v1/TenantWorkspace/ListTenantWorkspaces",
            body={"page": 1, "limit": 1},
        )
        workspaces = _items(response)
        if not workspaces:
            raise ValueError("No tenant workspace is available for dataset storage")
        workspace = workspaces[0]
        if "datahub_bucket" not in workspace:
            raise ValueError("Tenant workspace does not expose datahub_bucket")
        return workspace


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
        data = response.get("items")
        if isinstance(data, list):
            return data
        data = response.get("data")
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                return items
    return []

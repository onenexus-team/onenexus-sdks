import os
import shutil
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .cas_storage import create_runtime_s3_credential
from ..config import CAS_S3_ROLE_NAME, S3_ENDPOINT_URL
from ..errors import OneNexusAPIError, ProblemType
from .http import APIClient
from .results import (
    InternalDownloadResult as DownloadResult,
    InternalUploadResult as UploadResult,
)
from .storage import StorageTransferFile, download_prefix, upload_path

DOWNLOADABLE_DATASET_STATUSES = frozenset({"FINALIZED", "READY", "IN_USE"})


class DataHubTransferClient:
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
    ) -> UploadResult[dict[str, Any]]:
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
    ) -> UploadResult[dict[str, Any]]:
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

    def _fail_dataset_upload_best_effort(
        self, dataset_id: str, error: Exception
    ) -> None:
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
    ) -> DownloadResult[dict[str, Any]]:
        dataset = self.get_dataset(dataset_id)
        _require_downloadable_dataset(dataset_id, dataset)
        credential = self._create_dataset_runtime_credential(dataset_id=dataset_id)
        destination = Path(destination_path).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        staging = destination / f".nexusai-download-{uuid4().hex}"
        try:
            staged_files = download_prefix(staging, credential)
            # A delete may have started while objects were being copied, so
            # the staged copy is published only if the dataset is still
            # downloadable once the copy is complete.
            _require_downloadable_dataset(dataset_id, self.get_dataset(dataset_id))
            files = _publish_staged_files(staged_files, staging, destination)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return DownloadResult(resource=dataset, files=files)

    def _create_dataset_runtime_credential(self, dataset_id: str) -> dict[str, Any]:
        target = self._api.post_dict(
            "/protected/v1/DataHub/GetDatasetTransferTarget",
            body={"dataset_id": dataset_id},
        )
        return create_runtime_s3_credential(
            cas_client_factory=self._cas_client_factory,
            role_name=self._s3_role_name,
            endpoint_url=self._s3_endpoint_url,
            bucket=str(target["bucket"]),
            prefix=str(target["prefix"]),
            retry_policy=self._api.retry_policy,
        )


def _require_downloadable_dataset(dataset_id: str, dataset: dict[str, Any]) -> None:
    status = str(dataset.get("status") or "").upper()
    if status not in DOWNLOADABLE_DATASET_STATUSES:
        raise OneNexusAPIError(
            409,
            "Conflict",
            f"Dataset {dataset_id} cannot be downloaded while its status is "
            f"{status or 'unknown'}",
            problem_type=ProblemType.INVALID_STATE,
        )


def _publish_staged_files(
    staged_files: Iterable[StorageTransferFile],
    staging: Path,
    destination: Path,
) -> list[StorageTransferFile]:
    published: list[StorageTransferFile] = []
    for file in staged_files:
        relative_path = Path(file.local_path).relative_to(staging)
        local_path = (destination / relative_path).resolve()
        if not local_path.is_relative_to(destination):
            raise ValueError(
                f"Unsafe object key returned by storage: {file.object_key!r}"
            )
        local_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(file.local_path, local_path)
        published.append(replace(file, local_path=str(local_path)))
    return published


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

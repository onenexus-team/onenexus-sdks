from typing import Any, Optional

from .http import APIClient


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class DataHubWorkloadClient:
    def __init__(self, api: APIClient):
        self._api = api

    def acquire_dataset_reader_lease(
        self,
        dataset_id: str,
        owner_resource_type: str,
        owner_resource_id: str,
        lease_ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/DataHub/AcquireDatasetReaderLease",
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
            "/v1/DataHub/HeartbeatDatasetReaderLease",
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
            "/v1/DataHub/ReleaseDatasetReaderLease",
            body={
                "dataset_id": dataset_id,
                "reader_lease_id": reader_lease_id,
            },
        )


class ModelRegistryWorkloadClient:
    def __init__(self, api: APIClient):
        self._api = api

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
            "/v1/ModelRegistry/AcquireModelVersionReaderLease",
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
            "/v1/ModelRegistry/HeartbeatModelVersionReaderLease",
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
            "/v1/ModelRegistry/ReleaseModelVersionReaderLease",
            body={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "reader_lease_id": reader_lease_id,
            },
        )


class TrainingWorkloadClient:
    def __init__(self, api: APIClient):
        self._api = api

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
            "/v1/Training/AcquireRunCheckpointReaderLease",
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
            "/v1/Training/HeartbeatRunCheckpointReaderLease",
            body={
                "reader_lease_id": reader_lease_id,
                "lease_ttl_seconds": lease_ttl_seconds,
            },
        )

    def release_checkpoint_reader_lease(self, reader_lease_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Training/ReleaseRunCheckpointReaderLease",
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
            "/v1/Training/AcquireRunTokenizerReaderLease",
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
            "/v1/Training/HeartbeatRunTokenizerReaderLease",
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
            "/v1/Training/ReleaseRunTokenizerReaderLease",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "reader_lease_id": reader_lease_id,
            },
        )


class WorkloadClient:
    def __init__(self, api: APIClient):
        self.data_hub = DataHubWorkloadClient(api)
        self.model_registry = ModelRegistryWorkloadClient(api)
        self.training = TrainingWorkloadClient(api)


InternalWorkloadClient = WorkloadClient

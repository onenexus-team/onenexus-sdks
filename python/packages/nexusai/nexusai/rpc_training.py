from typing import Any, Optional

from .config import DEFAULT_EXPIRES_IN
from .http import APIClient


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class RpcTrainingClient:
    def __init__(self, api: APIClient):
        self._api = api

    def create_experiment(
        self,
        name: str,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
            "/v1/Training/GetExperiment",
            body={"experiment_id": experiment_id},
        )

    def update_experiment(
        self,
        experiment_id: str,
        name: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
            "/v1/Training/GetRun",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def stop_run(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/Training/StopRun",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def cancel_run(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/Training/CancelRun",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def delete_run(self, experiment_id: str, run_id: str) -> dict[str, Any]:
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
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
        return self._api.post(
            "/v1/Training/ListRunCheckpoints",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def create_run_checkpoint(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/Training/CreateRunCheckpoint",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
            },
        )

    def delete_run_checkpoints(
        self,
        experiment_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/Training/DeleteRunCheckpoints",
            body={"experiment_id": experiment_id, "run_id": run_id},
        )

    def list_run_checkpoint_files(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
    ) -> list[dict[str, Any]]:
        return self._api.post(
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
        return self._api.post(
            "/v1/Training/DeleteRunCheckpoint",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
            },
        )

    def create_checkpoint_upload_credential(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/Training/UploadRunCheckpoint",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
                "expires_in": expires_in,
            },
        )

    def create_checkpoint_download_credential(
        self,
        experiment_id: str,
        run_id: str,
        checkpoint_name: str,
        expires_in: int = DEFAULT_EXPIRES_IN,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/Training/DownloadRunCheckpoint",
            body={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
                "expires_in": expires_in,
            },
        )

from typing import Any, Optional

from .http import APIClient


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class RpcInferenceClient:
    def __init__(self, api: APIClient):
        self._api = api

    def create_inference_instance(
        self,
        name: str,
        model_id: str,
        served_model_name: str,
        flavor: str,
        model_version_id: Optional[str] = None,
        configuration: Optional[dict[str, Any]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/CreateInferenceInstance",
            body=_clean(
                {
                    "name": name,
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "served_model_name": served_model_name,
                    "flavor": flavor,
                    "configuration": configuration or {},
                    "extras_data": extras_data,
                }
            ),
        )

    def list_inference_instances(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        model_id: Optional[str] = None,
        model_version_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post_list(
            "/v1/Inference/ListInferenceInstances",
            body=_clean(
                {
                    "page": page,
                    "limit": limit,
                    "name": name,
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "status": status,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ),
        )

    def get_inference_instance(self, inference_instance_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/GetInferenceInstance",
            body={"inference_instance_id": inference_instance_id},
        )

    def update_inference_instance(
        self,
        inference_instance_id: str,
        name: Optional[str] = None,
        model_id: Optional[str] = None,
        model_version_id: Optional[str] = None,
        clear_model_version_id: bool = False,
        served_model_name: Optional[str] = None,
        flavor: Optional[str] = None,
        configuration: Optional[dict[str, Any]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/UpdateInferenceInstance",
            body=_clean(
                {
                    "inference_instance_id": inference_instance_id,
                    "name": name,
                    "model_id": model_id,
                    "model_version_id": model_version_id,
                    "clear_model_version_id": clear_model_version_id,
                    "served_model_name": served_model_name,
                    "flavor": flavor,
                    "configuration": configuration,
                    "extras_data": extras_data,
                }
            ),
        )

    def stop_inference_instance(self, inference_instance_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/StopInferenceInstance",
            body={"inference_instance_id": inference_instance_id},
        )

    def restart_inference_instance(self, inference_instance_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/RestartInferenceInstance",
            body={"inference_instance_id": inference_instance_id},
        )

    def finalize_inference_instance(self, inference_instance_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/FinalizeInferenceInstance",
            body={"inference_instance_id": inference_instance_id},
        )

    def delete_inference_instance(self, inference_instance_id: str) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/DeleteInferenceInstance",
            body={"inference_instance_id": inference_instance_id},
        )

    def get_inference_instance_endpoint(
        self, inference_instance_id: str
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/GetInferenceInstanceEndpoint",
            body={"inference_instance_id": inference_instance_id},
        )

    def get_inference_instance_logs(
        self,
        inference_instance_id: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/GetInferenceInstanceLogs",
            body=_clean(
                {
                    "inference_instance_id": inference_instance_id,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                }
            ),
        )

    def get_inference_instance_metrics(
        self,
        inference_instance_id: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post_dict(
            "/v1/Inference/GetInferenceInstanceMetrics",
            body=_clean(
                {
                    "inference_instance_id": inference_instance_id,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                }
            ),
        )

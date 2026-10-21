from typing import Any, Optional

from ._internal.http import APIClient
from .models import (
    InferenceActionResult,
    InferenceEndpoint,
    InferenceInstanceDetail,
    InferenceInstanceSummary,
    InferenceLogsResult,
    InferenceMetricsResult,
    Page,
)
from .wait import WaitPolicy, wait_for_status


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class InferenceClient:
    def __init__(self, api: APIClient) -> None:
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
    ) -> InferenceActionResult:
        return self._api.post_model(
            "/v1/Inference/CreateInferenceInstance",
            InferenceActionResult,
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
    ) -> Page[InferenceInstanceSummary]:
        return self._api.post_page(
            "/v1/Inference/ListInferenceInstances",
            InferenceInstanceSummary,
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

    def get_inference_instance(
        self,
        inference_instance_id: str,
    ) -> InferenceInstanceDetail:
        return self._api.post_model(
            "/v1/Inference/GetInferenceInstance",
            InferenceInstanceDetail,
            body={"inference_instance_id": inference_instance_id},
        )

    def wait_for_inference_instance(
        self,
        inference_instance_id: str,
        *,
        target_statuses: set[str] | frozenset[str] = frozenset(
            {"RUNNING", "FAILED", "STOPPED", "FINALIZED"}
        ),
        policy: WaitPolicy | None = None,
    ) -> InferenceInstanceDetail:
        return wait_for_status(
            lambda: self.get_inference_instance(inference_instance_id),
            status_of=lambda instance: instance.status,
            target_statuses=target_statuses,
            policy=policy or WaitPolicy(),
            description=f"inference instance {inference_instance_id}",
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
    ) -> InferenceActionResult:
        return self._api.post_model(
            "/v1/Inference/UpdateInferenceInstance",
            InferenceActionResult,
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

    def stop_inference_instance(
        self, inference_instance_id: str
    ) -> InferenceActionResult:
        return self._action("StopInferenceInstance", inference_instance_id)

    def restart_inference_instance(
        self, inference_instance_id: str
    ) -> InferenceActionResult:
        return self._action("RestartInferenceInstance", inference_instance_id)

    def finalize_inference_instance(
        self, inference_instance_id: str
    ) -> InferenceActionResult:
        return self._action("FinalizeInferenceInstance", inference_instance_id)

    def delete_inference_instance(
        self, inference_instance_id: str
    ) -> Optional[InferenceActionResult]:
        return self._api.post_optional_model(
            "/v1/Inference/DeleteInferenceInstance",
            InferenceActionResult,
            body={"inference_instance_id": inference_instance_id},
        )

    def get_inference_instance_endpoint(
        self,
        inference_instance_id: str,
    ) -> InferenceEndpoint:
        return self._api.post_model(
            "/v1/Inference/GetInferenceInstanceEndpoint",
            InferenceEndpoint,
            body={"inference_instance_id": inference_instance_id},
        )

    def get_inference_instance_logs(
        self,
        inference_instance_id: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> InferenceLogsResult:
        return self._api.post_model(
            "/v1/Inference/GetInferenceInstanceLogs",
            InferenceLogsResult,
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
    ) -> InferenceMetricsResult:
        return self._api.post_model(
            "/v1/Inference/GetInferenceInstanceMetrics",
            InferenceMetricsResult,
            body=_clean(
                {
                    "inference_instance_id": inference_instance_id,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp,
                }
            ),
        )

    def _action(
        self, operation: str, inference_instance_id: str
    ) -> InferenceActionResult:
        return self._api.post_model(
            f"/v1/Inference/{operation}",
            InferenceActionResult,
            body={"inference_instance_id": inference_instance_id},
        )

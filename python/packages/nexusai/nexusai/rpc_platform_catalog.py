from typing import Any, Optional

from .http import APIClient


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class RpcPlatformCatalogClient:
    def __init__(self, api: APIClient):
        self._api = api

    def create_workload_image(
        self,
        name: str,
        service: str,
        type: str,
        url: str,
        priority: int = 0,
        mock: bool = False,
        latest: bool = False,
        image_secret: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/CreateWorkloadImage",
            body=_clean(locals_without_self(locals())),
        )

    def list_workload_images(
        self,
        name: Optional[str] = None,
        service: Optional[str] = None,
        type: Optional[str] = None,
        mock: Optional[bool] = None,
        latest: Optional[bool] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post(
            "/v1/PlatformCatalog/ListWorkloadImages",
            body=_clean(locals_without_self(locals())),
        )

    def get_latest_workload_image(
        self,
        service: str,
        type: Optional[str] = None,
        mock: Optional[bool] = None,
        training_type: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/GetLatestWorkloadImage",
            body=_clean(locals_without_self(locals())),
        )

    def get_workload_image(self, workload_image_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/GetWorkloadImage",
            body={"workload_image_id": workload_image_id},
        )

    def update_workload_image(
        self,
        workload_image_id: str,
        name: Optional[str] = None,
        priority: Optional[int] = None,
        service: Optional[str] = None,
        type: Optional[str] = None,
        mock: Optional[bool] = None,
        url: Optional[str] = None,
        latest: Optional[bool] = None,
        image_secret: Optional[str] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/UpdateWorkloadImage",
            body=_clean(locals_without_self(locals())),
        )

    def set_latest_workload_image(self, workload_image_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/SetLatestWorkloadImage",
            body={"workload_image_id": workload_image_id},
        )

    def delete_workload_image(self, workload_image_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/DeleteWorkloadImage",
            body={"workload_image_id": workload_image_id},
        )

    def create_flavor(
        self,
        name: str,
        gpus: int,
        cpus: str,
        memory: str,
        nodes: int,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/CreateFlavor",
            body=_clean(locals_without_self(locals())),
        )

    def list_flavors(
        self,
        name: Optional[str] = None,
        min_gpus: Optional[int] = None,
        max_gpus: Optional[int] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post(
            "/v1/PlatformCatalog/ListFlavors",
            body=_clean(locals_without_self(locals())),
        )

    def get_flavor(self, flavor_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/GetFlavor",
            body={"flavor_id": flavor_id},
        )

    def update_flavor(
        self,
        flavor_id: str,
        name: Optional[str] = None,
        gpus: Optional[int] = None,
        cpus: Optional[str] = None,
        memory: Optional[str] = None,
        nodes: Optional[int] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/UpdateFlavor",
            body=_clean(locals_without_self(locals())),
        )

    def delete_flavor(self, flavor_id: str) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/DeleteFlavor",
            body={"flavor_id": flavor_id},
        )

    def create_training_configuration(
        self,
        training_type: str,
        default_hyperparameters: Optional[dict[str, Any]] = None,
        default_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        default_mock_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/CreateTrainingConfiguration",
            body=_clean(locals_without_self(locals())),
        )

    def list_training_configurations(
        self,
        training_type: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post(
            "/v1/PlatformCatalog/ListTrainingConfigurations",
            body=_clean(locals_without_self(locals())),
        )

    def get_training_configuration(
        self,
        training_configuration_id: str,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/GetTrainingConfiguration",
            body={"training_configuration_id": training_configuration_id},
        )

    def update_training_configuration(
        self,
        training_configuration_id: str,
        training_type: Optional[str] = None,
        default_hyperparameters: Optional[dict[str, Any]] = None,
        default_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        default_mock_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/UpdateTrainingConfiguration",
            body=_clean(locals_without_self(locals())),
        )

    def delete_training_configuration(
        self,
        training_configuration_id: str,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/DeleteTrainingConfiguration",
            body={"training_configuration_id": training_configuration_id},
        )

    def create_inference_configuration(
        self,
        runtime: str,
        default_configuration: Optional[dict[str, Any]] = None,
        default_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        default_mock_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/CreateInferenceConfiguration",
            body=_clean(locals_without_self(locals())),
        )

    def list_inference_configurations(
        self,
        runtime: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.post(
            "/v1/PlatformCatalog/ListInferenceConfigurations",
            body=_clean(locals_without_self(locals())),
        )

    def get_inference_configuration(
        self,
        inference_configuration_id: str,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/GetInferenceConfiguration",
            body={"inference_configuration_id": inference_configuration_id},
        )

    def update_inference_configuration(
        self,
        inference_configuration_id: str,
        runtime: Optional[str] = None,
        default_configuration: Optional[dict[str, Any]] = None,
        default_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        default_mock_workload_image_workflow: Optional[list[dict[str, Any]]] = None,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/UpdateInferenceConfiguration",
            body=_clean(locals_without_self(locals())),
        )

    def delete_inference_configuration(
        self,
        inference_configuration_id: str,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/PlatformCatalog/DeleteInferenceConfiguration",
            body={"inference_configuration_id": inference_configuration_id},
        )


def locals_without_self(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key != "self"}

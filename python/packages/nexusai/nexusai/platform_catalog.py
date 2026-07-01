from typing import Any, Optional

from .http import APIClient


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class PlatformCatalogClient:
    def __init__(self, api: APIClient):
        self._api = api

    def create_workload_image(self, **body) -> dict[str, Any]:
        return self._api.post("/v1/platform-catalog/workload-images", body=_clean(body))

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
        return self._api.get(
            "/v1/platform-catalog/workload-images",
            params=_clean(locals_without_self(locals())),
        )

    def get_latest_workload_image(
        self,
        service: str,
        type: Optional[str] = None,
        mock: Optional[bool] = None,
        training_type: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._api.get(
            "/v1/platform-catalog/workload-images/latest",
            params=_clean(locals_without_self(locals())),
        )

    def get_workload_image(self, workload_image_id: str) -> dict[str, Any]:
        return self._api.get(f"/v1/platform-catalog/workload-images/{workload_image_id}")

    def update_workload_image(self, workload_image_id: str, **body) -> dict[str, Any]:
        return self._api.patch(
            f"/v1/platform-catalog/workload-images/{workload_image_id}",
            body=_clean(body),
        )

    def set_latest_workload_image(self, workload_image_id: str) -> dict[str, Any]:
        return self._api.post(
            f"/v1/platform-catalog/workload-images/{workload_image_id}/latest"
        )

    def delete_workload_image(self, workload_image_id: str) -> dict[str, Any]:
        return self._api.delete(
            f"/v1/platform-catalog/workload-images/{workload_image_id}"
        )

    def create_flavor(self, **body) -> dict[str, Any]:
        return self._api.post("/v1/platform-catalog/flavors", body=_clean(body))

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
        return self._api.get(
            "/v1/platform-catalog/flavors",
            params=_clean(locals_without_self(locals())),
        )

    def get_flavor(self, flavor_id: str) -> dict[str, Any]:
        return self._api.get(f"/v1/platform-catalog/flavors/{flavor_id}")

    def update_flavor(self, flavor_id: str, **body) -> dict[str, Any]:
        return self._api.patch(
            f"/v1/platform-catalog/flavors/{flavor_id}",
            body=_clean(body),
        )

    def delete_flavor(self, flavor_id: str) -> dict[str, Any]:
        return self._api.delete(f"/v1/platform-catalog/flavors/{flavor_id}")

    def create_training_configuration(self, **body) -> dict[str, Any]:
        return self._api.post(
            "/v1/platform-catalog/training-configurations",
            body=_clean(body),
        )

    def list_training_configurations(
        self,
        training_type: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.get(
            "/v1/platform-catalog/training-configurations",
            params=_clean(locals_without_self(locals())),
        )

    def get_training_configuration(self, training_configuration_id: str) -> dict[str, Any]:
        return self._api.get(
            f"/v1/platform-catalog/training-configurations/{training_configuration_id}"
        )

    def update_training_configuration(
        self,
        training_configuration_id: str,
        **body,
    ) -> dict[str, Any]:
        return self._api.patch(
            f"/v1/platform-catalog/training-configurations/{training_configuration_id}",
            body=_clean(body),
        )

    def delete_training_configuration(
        self,
        training_configuration_id: str,
    ) -> dict[str, Any]:
        return self._api.delete(
            f"/v1/platform-catalog/training-configurations/{training_configuration_id}"
        )

    def create_inference_configuration(self, **body) -> dict[str, Any]:
        return self._api.post(
            "/v1/platform-catalog/inference-configurations",
            body=_clean(body),
        )

    def list_inference_configurations(
        self,
        runtime: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.get(
            "/v1/platform-catalog/inference-configurations",
            params=_clean(locals_without_self(locals())),
        )

    def get_inference_configuration(self, inference_configuration_id: str) -> dict[str, Any]:
        return self._api.get(
            f"/v1/platform-catalog/inference-configurations/{inference_configuration_id}"
        )

    def update_inference_configuration(
        self,
        inference_configuration_id: str,
        **body,
    ) -> dict[str, Any]:
        return self._api.patch(
            f"/v1/platform-catalog/inference-configurations/{inference_configuration_id}",
            body=_clean(body),
        )

    def delete_inference_configuration(
        self,
        inference_configuration_id: str,
    ) -> dict[str, Any]:
        return self._api.delete(
            f"/v1/platform-catalog/inference-configurations/{inference_configuration_id}"
        )


def locals_without_self(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key != "self"}

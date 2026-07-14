from typing import Any, Optional

from ._internal.http import APIClient
from .models import Flavor, InferenceConfiguration, Page, TrainingConfiguration


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class PlatformCatalogClient:
    """Public, selectable platform options.

    Administrative workload-image and catalog mutation APIs are intentionally
    not part of the public SDK surface.
    """

    def __init__(self, api: APIClient) -> None:
        self._api = api

    def list_flavors(
        self,
        name: Optional[str] = None,
        min_gpus: Optional[int] = None,
        max_gpus: Optional[int] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[Flavor]:
        return self._api.post_page(
            "/v1/PlatformCatalog/ListFlavors",
            Flavor,
            body=_clean(
                {
                    "name": name,
                    "min_gpus": min_gpus,
                    "max_gpus": max_gpus,
                    "page": page,
                    "limit": limit,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ),
        )

    def get_flavor(self, flavor_id: str) -> Flavor:
        return self._api.post_model(
            "/v1/PlatformCatalog/GetFlavor",
            Flavor,
            body={"flavor_id": flavor_id},
        )

    def list_training_configurations(
        self,
        training_type: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[TrainingConfiguration]:
        return self._api.post_page(
            "/v1/PlatformCatalog/ListTrainingConfigurations",
            TrainingConfiguration,
            body=_clean(
                {
                    "training_type": training_type,
                    "page": page,
                    "limit": limit,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ),
        )

    def get_training_configuration(
        self,
        training_configuration_id: str,
    ) -> TrainingConfiguration:
        return self._api.post_model(
            "/v1/PlatformCatalog/GetTrainingConfiguration",
            TrainingConfiguration,
            body={"training_configuration_id": training_configuration_id},
        )

    def list_inference_configurations(
        self,
        runtime: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[InferenceConfiguration]:
        return self._api.post_page(
            "/v1/PlatformCatalog/ListInferenceConfigurations",
            InferenceConfiguration,
            body=_clean(
                {
                    "runtime": runtime,
                    "page": page,
                    "limit": limit,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ),
        )

    def get_inference_configuration(
        self,
        inference_configuration_id: str,
    ) -> InferenceConfiguration:
        return self._api.post_model(
            "/v1/PlatformCatalog/GetInferenceConfiguration",
            InferenceConfiguration,
            body={"inference_configuration_id": inference_configuration_id},
        )

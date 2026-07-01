from typing import Any, Optional

from .http import APIClient


def _clean(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


class TenantWorkspaceClient:
    def __init__(self, api: APIClient):
        self._api = api

    def create_tenant_workspace(
        self,
        name: str,
        model_registry_bucket: str,
        datahub_bucket: str,
        checkpoint_bucket: str,
        tokenizer_bucket: str,
        tenant_gpus_quota: int = 16,
        extras_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._api.post(
            "/v1/tenant-workspaces",
            body=_clean(
                {
                    "name": name,
                    "model_registry_bucket": model_registry_bucket,
                    "datahub_bucket": datahub_bucket,
                    "checkpoint_bucket": checkpoint_bucket,
                    "tokenizer_bucket": tokenizer_bucket,
                    "tenant_gpus_quota": tenant_gpus_quota,
                    "extras_data": extras_data,
                }
            ),
        )

    def get_tenant_workspace(self, workspace_id: str) -> dict[str, Any]:
        return self._api.get(f"/v1/tenant-workspaces/{workspace_id}")

    def list_tenant_workspaces(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self._api.get(
            "/v1/tenant-workspaces",
            params=_clean(
                {
                    "page": page,
                    "limit": limit,
                    "name": name,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ),
        )

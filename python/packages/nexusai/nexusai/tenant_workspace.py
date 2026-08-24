from typing import Any, Optional

from ._internal.http import APIClient
from .models import Page, TenantWorkspaceDetail, TenantWorkspaceSummary


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
        extras_data: Optional[dict[str, Any]] = None,
    ) -> TenantWorkspaceDetail:
        return self._api.post_model(
            "/v1/TenantWorkspace/CreateTenantWorkspace",
            TenantWorkspaceDetail,
            body=_clean(
                {
                    "name": name,
                    "model_registry_bucket": model_registry_bucket,
                    "datahub_bucket": datahub_bucket,
                    "checkpoint_bucket": checkpoint_bucket,
                    "tokenizer_bucket": tokenizer_bucket,
                    "extras_data": extras_data,
                }
            ),
        )

    def get_tenant_workspace(self, workspace_id: str) -> TenantWorkspaceDetail:
        return self._api.post_model(
            "/v1/TenantWorkspace/GetTenantWorkspace",
            TenantWorkspaceDetail,
            body={"workspace_id": workspace_id},
        )

    def list_tenant_workspaces(
        self,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Page[TenantWorkspaceSummary]:
        return self._api.post_page(
            "/v1/TenantWorkspace/ListTenantWorkspaces",
            TenantWorkspaceSummary,
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

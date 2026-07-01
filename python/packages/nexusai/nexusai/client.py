from .cas import create_cas_client, credentials_from_access_token
from .config import CAS_BASE_URL, PLATFORM_API_BASE_URL, normalize_api_base_url
from .data_hub import DataHubClient as RestDataHubClient
from .http import APIClient
from .inference import InferenceClient as RestInferenceClient
from .model_registry import ModelRegistryClient as RestModelRegistryClient
from .platform_catalog import PlatformCatalogClient as RestPlatformCatalogClient
from .tenant_workspace import TenantWorkspaceClient as RestTenantWorkspaceClient
from .training import TrainingClient as RestTrainingClient
from .rpc_data_hub import RpcDataHubClient
from .rpc_inference import RpcInferenceClient
from .rpc_model_registry import RpcModelRegistryClient
from .rpc_platform_catalog import RpcPlatformCatalogClient
from .rpc_tenant_workspace import RpcTenantWorkspaceClient
from .rpc_training import RpcTrainingClient

SDK_API_STYLE_REST = "rest"
SDK_API_STYLE_RPC = "rpc"
SDK_API_STYLES = (SDK_API_STYLE_RPC, SDK_API_STYLE_REST)


class OneNexusClient:
    def __init__(
        self,
        personal_token: str | None = None,
        access_token: str | None = None,
        api_style: str = SDK_API_STYLE_RPC,
        base_url: str = PLATFORM_API_BASE_URL,
        cas_url: str = CAS_BASE_URL,
        timeout: float = 60.0,
    ):
        if api_style not in SDK_API_STYLES:
            raise ValueError(f"api_style must be one of: {', '.join(SDK_API_STYLES)}")

        token = access_token or personal_token
        if not token:
            raise ValueError("access_token or personal_token is required")

        self.api_style = api_style
        self.access_token = token
        self.personal_token = token
        self.cas_url = cas_url.rstrip("/")
        self._api = APIClient(
            personal_token=token,
            base_url=normalize_api_base_url(base_url),
            timeout=timeout,
        )
        if api_style == SDK_API_STYLE_RPC:
            self.platform_catalog = RpcPlatformCatalogClient(self._api)
            self.tenant_workspace = RpcTenantWorkspaceClient(self._api)
            self.data_hub = RpcDataHubClient(self._api)
            self.model_registry = RpcModelRegistryClient(self._api)
            self.training = RpcTrainingClient(self._api)
            self.inference = RpcInferenceClient(self._api)
        else:
            self.platform_catalog = RestPlatformCatalogClient(self._api)
            self.tenant_workspace = RestTenantWorkspaceClient(self._api)
            self.data_hub = RestDataHubClient(self._api)
            self.model_registry = RestModelRegistryClient(self._api)
            self.training = RestTrainingClient(self._api)
            self.inference = RestInferenceClient(self._api)

    def upload_dataset(self, *args, **kwargs):
        return self.data_hub.upload_dataset(*args, **kwargs)

    def download_dataset(self, *args, **kwargs):
        return self.data_hub.download_dataset(*args, **kwargs)

    def upload_model_version(self, *args, **kwargs):
        return self.model_registry.upload_model_version(*args, **kwargs)

    def upload_model_versiion(self, *args, **kwargs):
        return self.upload_model_version(*args, **kwargs)

    def upload_to_model_version(self, *args, **kwargs):
        return self.model_registry.upload_to_model_version(*args, **kwargs)

    def download_model(self, *args, **kwargs):
        return self.model_registry.download_model(*args, **kwargs)

    def download_model_dataset(self, *args, **kwargs):
        return self.download_dataset(*args, **kwargs)

    def cas_credentials(self):
        return credentials_from_access_token(self.access_token)

    def create_cas_client(self, *, cas_url: str | None = None, context=None, http_client=None):
        return create_cas_client(
            self.access_token,
            base_url=cas_url or self.cas_url,
            context=context,
            http_client=http_client,
        )


NexusAIClient = OneNexusClient

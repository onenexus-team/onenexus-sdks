import httpx
from onenexus_cas_client import CasClient
from onenexus_sdk_core import ClientContext, Credentials, default_client_context

from .cas import (
    create_cas_client_with_credentials,
    credentials_from_token,
)
from .config import (
    CAS_BASE_URL,
    CAS_S3_ROLE_NAME,
    PLATFORM_API_BASE_URL,
    S3_ENDPOINT_URL,
    normalize_api_base_url,
)
from .data_hub import DataHubClient
from ._internal.http import APIClient
from .inference import InferenceClient
from .model_registry import ModelRegistryClient
from .platform_catalog import PlatformCatalogClient
from .retry import RetryPolicy
from .tenant_workspace import TenantWorkspaceClient
from .training import TrainingClient


class OneNexusClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = PLATFORM_API_BASE_URL,
        cas_url: str = CAS_BASE_URL,
        s3_endpoint_url: str = S3_ENDPOINT_URL,
        s3_role_name: str = CAS_S3_ROLE_NAME,
        timeout: float = 60.0,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not token:
            raise ValueError("token is required")

        self._configure(
            token=token,
            credentials=credentials_from_token(token),
            base_url=base_url,
            cas_url=cas_url,
            s3_endpoint_url=s3_endpoint_url,
            s3_role_name=s3_role_name,
            timeout=timeout,
            retry_policy=retry_policy,
        )

    @classmethod
    def from_credentials(
        cls,
        credentials: Credentials,
        *,
        base_url: str = PLATFORM_API_BASE_URL,
        cas_url: str = CAS_BASE_URL,
        s3_endpoint_url: str = S3_ENDPOINT_URL,
        s3_role_name: str = CAS_S3_ROLE_NAME,
        timeout: float = 60.0,
        retry_policy: RetryPolicy | None = None,
    ) -> "OneNexusClient":
        client = cls.__new__(cls)
        client._configure(
            token=None,
            credentials=credentials,
            base_url=base_url,
            cas_url=cas_url,
            s3_endpoint_url=s3_endpoint_url,
            s3_role_name=s3_role_name,
            timeout=timeout,
            retry_policy=retry_policy,
        )
        return client

    _from_credentials = from_credentials

    def _configure(
        self,
        *,
        token: str | None,
        credentials: Credentials,
        base_url: str,
        cas_url: str,
        s3_endpoint_url: str,
        s3_role_name: str,
        timeout: float,
        retry_policy: RetryPolicy | None,
    ) -> None:

        self.token = token
        self._credentials = credentials
        self._context = default_client_context()
        self.cas_url = cas_url.rstrip("/")
        self.s3_endpoint_url = s3_endpoint_url
        self.s3_role_name = s3_role_name
        self._api = APIClient(
            credentials=credentials,
            context=self._context,
            base_url=normalize_api_base_url(base_url),
            timeout=timeout,
            retry_policy=retry_policy,
        )

        def cas_client_factory() -> CasClient:
            return create_cas_client_with_credentials(
                credentials,
                base_url=self.cas_url,
            )

        self.platform_catalog = PlatformCatalogClient(self._api)
        self.tenant_workspace = TenantWorkspaceClient(self._api)
        self.data_hub = DataHubClient(
            self._api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=self.s3_endpoint_url,
            s3_role_name=self.s3_role_name,
        )
        self.model_registry = ModelRegistryClient(
            self._api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=self.s3_endpoint_url,
            s3_role_name=self.s3_role_name,
        )
        self.training = TrainingClient(
            self._api,
            cas_client_factory=cas_client_factory,
            s3_endpoint_url=self.s3_endpoint_url,
            s3_role_name=self.s3_role_name,
        )
        self.inference = InferenceClient(self._api)

    def create_cas_client(
        self,
        *,
        cas_url: str | None = None,
        context: ClientContext | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> CasClient:
        return create_cas_client_with_credentials(
            self._credentials,
            base_url=cas_url or self.cas_url,
            context=context or self._context,
            http_client=http_client,
        )


NexusAIClient = OneNexusClient

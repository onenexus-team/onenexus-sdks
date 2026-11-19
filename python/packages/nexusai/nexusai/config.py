import os


PLATFORM_BASE_URL = "https://ai-api-v3.ric1.onenexus-do.cloud"
PLATFORM_API_BASE_URL = f"{PLATFORM_BASE_URL}/api"
CAS_BASE_URL = "https://auth.onenexus-do.cloud"
S3_ENDPOINT_URL = os.getenv("ONENEXUS_S3_ENDPOINT_URL", "https://s3.onenexus-do.cloud")
CAS_S3_ROLE_NAME = os.getenv("ONENEXUS_CAS_S3_ROLE_NAME", "S3ObjectFullAccess")
DEFAULT_REGION = "us-east-1"
DEFAULT_EXPIRES_IN = 3600


def normalize_api_base_url(base_url: str) -> str:
    clean_url = base_url.rstrip("/")
    if clean_url.endswith("/api"):
        return clean_url
    return f"{clean_url}/api"

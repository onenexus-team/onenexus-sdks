PLATFORM_BASE_URL = "http://165.245.166.16:30210"
PLATFORM_API_BASE_URL = f"{PLATFORM_BASE_URL}/api"
CAS_BASE_URL = "https://cas.onenexus-do.cloud"
DEFAULT_REGION = "us-east-1"
DEFAULT_EXPIRES_IN = 3600


def normalize_api_base_url(base_url: str) -> str:
    clean_url = base_url.rstrip("/")
    if clean_url.endswith("/api"):
        return clean_url
    return f"{clean_url}/api"

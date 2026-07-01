import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import PLATFORM_API_BASE_URL
from .errors import OneNexusAPIError, OneNexusError


class APIClient:
    def __init__(
        self,
        personal_token: str,
        base_url: str = PLATFORM_API_BASE_URL,
        timeout: float = 60.0,
    ):
        if not personal_token:
            raise ValueError("personal_token is required")
        self.personal_token = personal_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        return self.request("GET", path, params=params)

    def post(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        return self.request("POST", path, body=body)

    def patch(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        return self.request("PATCH", path, body=body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def request(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = self._url(path, params=params)
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.personal_token}",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if response.status == 204:
                    return None
                return self._decode_response(response.read())
        except HTTPError as error:
            raise self._api_error(error) from error
        except URLError as error:
            raise OneNexusError(
                f"Could not connect to OneNexus API: {error}"
            ) from error

    def _url(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{clean_path}"
        query = {
            key: value for key, value in (params or {}).items() if value is not None
        }
        if query:
            url = f"{url}?{urlencode(query)}"
        return url

    def _decode_response(self, raw: bytes) -> Any:
        if not raw:
            return None
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def _api_error(self, error: HTTPError) -> OneNexusAPIError:
        payload = self._read_error_payload(error)
        detail = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            code = detail.get("code")
            message = detail.get("message") or error.reason
        else:
            code = None
            message = str(payload) if payload else error.reason
        return OneNexusAPIError(
            status_code=error.code,
            code=code,
            message=message,
            payload=payload if isinstance(payload, dict) else {},
        )

    @staticmethod
    def _read_error_payload(error: HTTPError) -> Any:
        raw = error.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw.decode("utf-8", errors="replace")

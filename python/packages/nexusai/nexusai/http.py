import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from onenexus_sdk_core import ClientContext, Credentials, default_client_context

from .cas import credentials_from_token
from .config import PLATFORM_API_BASE_URL
from .errors import OneNexusAPIError, OneNexusError


class APIClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = PLATFORM_API_BASE_URL,
        timeout: float = 60.0,
        *,
        credentials: Credentials | None = None,
        context: ClientContext | None = None,
    ) -> None:
        if bool(token) == bool(credentials):
            raise ValueError("provide exactly one of token or credentials")
        self.token = token
        self._credentials = credentials or credentials_from_token(str(token))
        self._context = context or default_client_context()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        return self._request("POST", path, body=body)

    def post_dict(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload = self.post(path, body)
        if not isinstance(payload, dict):
            raise OneNexusError(
                f"OneNexus API returned {type(payload).__name__}; expected object"
            )
        return payload

    def post_optional_dict(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        payload = self.post(path, body)
        if payload is not None and not isinstance(payload, dict):
            raise OneNexusError(
                f"OneNexus API returned {type(payload).__name__}; "
                "expected object or null"
            )
        return payload

    def post_list(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        payload = self.post(path, body)
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise OneNexusError(
                f"OneNexus API returned {type(payload).__name__}; "
                "expected a list of objects"
            )
        return payload

    def _request(
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
            "Authorization": self._authorization_header(),
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

    def _authorization_header(self) -> str:
        access_token = self._credentials.resolve_sync(self._context)
        return f"{access_token.token_type} {access_token.access_token}"

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

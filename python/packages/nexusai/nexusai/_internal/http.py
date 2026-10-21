import json
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Generic, Optional, TypeVar, cast
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from onenexus_sdk_core import ClientContext, Credentials, default_client_context

from .._version import __version__
from ..cas import credentials_from_token
from ..config import PLATFORM_API_BASE_URL
from ..errors import OneNexusAPIError, OneNexusError
from ..models import APIModel, Page
from ..retry import RetryPolicy


DataT = TypeVar("DataT")
ModelT = TypeVar("ModelT", bound=APIModel)


@dataclass(frozen=True)
class APIEnvelope(Generic[DataT]):
    data: DataT
    message: Optional[str] = None
    request_id: Optional[str] = None


@dataclass(frozen=True)
class APIListEnvelope(Generic[DataT]):
    items: list[DataT]
    total_pages: int
    message: Optional[str] = None
    request_id: Optional[str] = None


class APIClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = PLATFORM_API_BASE_URL,
        timeout: float = 60.0,
        *,
        credentials: Credentials | None = None,
        context: ClientContext | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if bool(token) == bool(credentials):
            raise ValueError("provide exactly one of token or credentials")
        self.token = token
        self._credentials = credentials or credentials_from_token(str(token))
        self._context = context or default_client_context()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()

    def post(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        return self.post_envelope(path, body).data

    def post_envelope(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> APIEnvelope[Any]:
        return cast(APIEnvelope[Any], self._request("POST", path, body=body))

    def post_list_envelope(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> APIListEnvelope[dict[str, Any]]:
        body = (
            {key: value for key, value in body.items() if value is not None}
            if body is not None
            else None
        )
        return cast(
            APIListEnvelope[dict[str, Any]],
            self._request("POST", path, body=body, list_response=True),
        )

    def post_model(
        self,
        path: str,
        model: type[ModelT],
        body: Optional[dict[str, Any]] = None,
    ) -> ModelT:
        payload = self.post_dict(path, body)
        return model.from_dict(payload)

    def post_optional_model(
        self,
        path: str,
        model: type[ModelT],
        body: Optional[dict[str, Any]] = None,
    ) -> Optional[ModelT]:
        payload = self.post_optional_dict(path, body)
        return model.from_dict(payload) if payload is not None else None

    def post_page(
        self,
        path: str,
        model: type[ModelT],
        body: Optional[dict[str, Any]] = None,
    ) -> Page[ModelT]:
        response = self.post_list_envelope(path, body)
        return Page(
            items=[model.from_dict(item) for item in response.items],
            total_pages=response.total_pages,
            message=response.message,
            request_id=response.request_id,
        )

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
        return self.post_list_envelope(path, body).items

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        list_response: bool = False,
    ) -> APIEnvelope[Any] | APIListEnvelope[Any]:
        url = self._url(path, params=params)
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": self._authorization_header(),
            "User-Agent": f"nexusai/{__version__}",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        operation_is_read_only = self._is_read_only_operation(method, path)
        idempotency_key = None
        if not operation_is_read_only:
            supplied_key = body.get("idempotency_key") if body else None
            if self._is_public_rpc_path(path) or supplied_key:
                idempotency_key = str(supplied_key or uuid4())
                headers["Idempotency-Key"] = idempotency_key

        retryable_operation = self._is_retryable_operation(
            operation_is_read_only=operation_is_read_only,
            idempotency_key=idempotency_key,
        )
        attempt = 1
        started_at = time.monotonic()
        while True:
            request = Request(url=url, data=data, headers=headers, method=method)
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    if response.status == 204:
                        return APIEnvelope(
                            data=None,
                            request_id=self._response_request_id(
                                getattr(response, "headers", None),
                            ),
                        )
                    decoder = (
                        self._decode_list_response
                        if list_response
                        else self._decode_response
                    )
                    return decoder(
                        response.read(),
                        request_id=self._response_request_id(
                            getattr(response, "headers", None),
                        ),
                    )
            except HTTPError as error:
                if not self._should_retry(
                    retryable_operation,
                    attempt,
                    started_at,
                    status_code=error.code,
                    idempotency_in_progress=self._is_idempotency_in_progress(error),
                ):
                    raise self._api_error(error) from error
                delay = self._retry_delay(attempt, error.headers.get("Retry-After"))
            except (URLError, TimeoutError) as error:
                if not self._should_retry(
                    retryable_operation,
                    attempt,
                    started_at,
                ):
                    raise OneNexusError(
                        f"Could not connect to OneNexus API: {error}"
                    ) from error
                delay = self._retry_delay(attempt)
            if time.monotonic() - started_at + delay > (
                self.retry_policy.max_elapsed_seconds
            ):
                raise OneNexusError("OneNexus API retry budget exhausted")
            time.sleep(delay)
            attempt += 1

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

    def _decode_response(
        self,
        raw: bytes,
        *,
        request_id: Optional[str] = None,
    ) -> APIEnvelope[Any]:
        if not raw:
            return APIEnvelope(data=None, request_id=request_id)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or "data" not in payload:
            raise OneNexusError("OneNexus API returned an invalid object envelope")
        return APIEnvelope(
            data=payload["data"],
            message=payload.get("message"),
            request_id=request_id,
        )

    def _decode_list_response(
        self,
        raw: bytes,
        *,
        request_id: Optional[str] = None,
    ) -> APIListEnvelope[Any]:
        if not raw:
            raise OneNexusError("OneNexus API returned an empty list response")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise OneNexusError("OneNexus API returned an invalid list envelope")
        items = payload.get("items")
        total_pages = payload.get("total_pages")
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            raise OneNexusError("OneNexus API returned invalid list items")
        if (
            isinstance(total_pages, bool)
            or not isinstance(total_pages, int)
            or total_pages < 0
        ):
            raise OneNexusError("OneNexus API returned invalid total_pages")
        return APIListEnvelope(
            items=items,
            total_pages=total_pages,
            message=payload.get("message"),
            request_id=request_id,
        )

    def _api_error(
        self,
        error: HTTPError,
    ) -> OneNexusAPIError:
        payload = self._read_error_payload(error)
        problem = payload if isinstance(payload, dict) else {}
        title = problem.get("title") or str(error.reason)
        detail = problem.get("detail") or title
        instance = problem.get("instance")
        return OneNexusAPIError(
            status_code=error.code,
            problem_type=problem.get("type"),
            title=title,
            detail=detail,
            instance=instance,
            payload=problem,
            request_id=self._response_request_id(error.headers)
            or self._request_id_from_instance(instance),
        )

    @staticmethod
    def _response_request_id(
        headers: Any,
    ) -> Optional[str]:
        if headers is None:
            return None
        value = headers.get("X-Request-ID")
        return str(value) if value else None

    @staticmethod
    def _request_id_from_instance(instance: Any) -> Optional[str]:
        prefix = "urn:onenexus:request:"
        if isinstance(instance, str) and instance.startswith(prefix):
            return instance.removeprefix(prefix)
        return None

    @staticmethod
    def _is_read_only_operation(
        method: str,
        path: str,
    ) -> bool:
        operation = path.rstrip("/").rsplit("/", maxsplit=1)[-1]
        return method.upper() == "GET" or operation.startswith(("Get", "List"))

    @staticmethod
    def _is_public_rpc_path(path: str) -> bool:
        return path.startswith("/v1/")

    def _is_retryable_operation(
        self,
        *,
        operation_is_read_only: bool,
        idempotency_key: Optional[str],
    ) -> bool:
        if not self.retry_policy.enabled:
            return False
        return operation_is_read_only or bool(idempotency_key)

    def _should_retry(
        self,
        operation_is_retryable: bool,
        attempt: int,
        started_at: float,
        *,
        status_code: Optional[int] = None,
        idempotency_in_progress: bool = False,
    ) -> bool:
        if not operation_is_retryable or attempt >= self.retry_policy.max_attempts:
            return False
        if time.monotonic() - started_at >= self.retry_policy.max_elapsed_seconds:
            return False
        return (
            status_code is None
            or status_code in {408, 429}
            or status_code >= 500
            or idempotency_in_progress
        )

    @staticmethod
    def _is_idempotency_in_progress(error: HTTPError) -> bool:
        if error.code != 409 or error.headers is None:
            return False
        return error.headers.get("X-Idempotency-Status") == "idempotency_in_progress"

    def _retry_delay(
        self,
        attempt: int,
        retry_after: Optional[str] = None,
    ) -> float:
        parsed_retry_after = self._parse_retry_after(retry_after)
        if parsed_retry_after is not None:
            return min(parsed_retry_after, self.retry_policy.max_delay_seconds)
        ceiling = min(
            self.retry_policy.base_delay_seconds * (2 ** (attempt - 1)),
            self.retry_policy.max_delay_seconds,
        )
        return random.uniform(0, ceiling)

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return max(float(value), 0.0)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max((retry_at - datetime.now(UTC)).total_seconds(), 0.0)

    @staticmethod
    def _read_error_payload(error: HTTPError) -> Any:
        raw = error.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw.decode("utf-8", errors="replace")

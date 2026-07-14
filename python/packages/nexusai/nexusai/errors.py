from typing import Any, Optional


class OneNexusError(Exception):
    pass


class OneNexusAPIError(OneNexusError):
    def __init__(
        self,
        status_code: int,
        message: str,
        code: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.payload = payload or {}
        self.request_id = request_id
        super().__init__(f"{status_code} {code or ''} {message}".strip())

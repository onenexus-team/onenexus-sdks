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
    ):
        self.status_code = status_code
        self.code = code
        self.payload = payload or {}
        super().__init__(f"{status_code} {code or ''} {message}".strip())

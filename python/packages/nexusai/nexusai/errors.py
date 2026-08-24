from enum import StrEnum
from typing import Any, Optional


class ProblemType(StrEnum):
    INVALID_REQUEST = "https://api.onenexus.vn/problems/invalid-request"
    IDEMPOTENCY_KEY_INVALID = "https://api.onenexus.vn/problems/idempotency-key-invalid"
    UNAUTHENTICATED = "https://api.onenexus.vn/problems/unauthenticated"
    FORBIDDEN = "https://api.onenexus.vn/problems/forbidden"
    RESOURCE_NOT_FOUND = "https://api.onenexus.vn/problems/resource-not-found"
    RESOURCE_CONFLICT = "https://api.onenexus.vn/problems/resource-conflict"
    INVALID_STATE = "https://api.onenexus.vn/problems/invalid-state"
    QUOTA_EXCEEDED = "https://api.onenexus.vn/problems/quota-exceeded"
    OPERATION_IN_PROGRESS = "https://api.onenexus.vn/problems/operation-in-progress"
    IDEMPOTENCY_KEY_REUSED = "https://api.onenexus.vn/problems/idempotency-key-reused"
    PAYLOAD_TOO_LARGE = "https://api.onenexus.vn/problems/payload-too-large"
    VALIDATION_FAILED = "https://api.onenexus.vn/problems/validation-failed"
    RATE_LIMITED = "https://api.onenexus.vn/problems/rate-limited"
    DEPENDENCY_UNAVAILABLE = "https://api.onenexus.vn/problems/dependency-unavailable"
    NOT_IMPLEMENTED = "https://api.onenexus.vn/problems/not-implemented"
    INTERNAL_ERROR = "https://api.onenexus.vn/problems/internal-error"


class OneNexusError(Exception):
    pass


class OneNexusAPIError(OneNexusError):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        problem_type: Optional[str] = None,
        instance: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        self.status_code = status_code
        self.problem_type = problem_type
        self.title = title
        self.detail = detail
        self.instance = instance
        self.payload = payload or {}
        self.request_id = request_id
        super().__init__(
            f"{status_code} {problem_type or 'about:blank'} {title}: {detail}"
        )

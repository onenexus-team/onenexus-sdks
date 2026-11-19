from enum import StrEnum
from typing import Any, Optional

PROBLEM_BASE_URL = "https://api-mlops.onenexus.cloud/problems"
# Comparison-only compatibility token. The SDK never dereferences problem URIs.
LEGACY_PROBLEM_BASE_URL = "https://api.onenexus.vn/problems"


class ProblemType(StrEnum):
    INVALID_REQUEST = f"{PROBLEM_BASE_URL}/invalid-request"
    IDEMPOTENCY_KEY_INVALID = f"{PROBLEM_BASE_URL}/idempotency-key-invalid"
    UNAUTHENTICATED = f"{PROBLEM_BASE_URL}/unauthenticated"
    FORBIDDEN = f"{PROBLEM_BASE_URL}/forbidden"
    RESOURCE_NOT_FOUND = f"{PROBLEM_BASE_URL}/resource-not-found"
    RESOURCE_CONFLICT = f"{PROBLEM_BASE_URL}/resource-conflict"
    INVALID_STATE = f"{PROBLEM_BASE_URL}/invalid-state"
    QUOTA_EXCEEDED = f"{PROBLEM_BASE_URL}/quota-exceeded"
    OPERATION_IN_PROGRESS = f"{PROBLEM_BASE_URL}/operation-in-progress"
    IDEMPOTENCY_KEY_REUSED = f"{PROBLEM_BASE_URL}/idempotency-key-reused"
    PAYLOAD_TOO_LARGE = f"{PROBLEM_BASE_URL}/payload-too-large"
    VALIDATION_FAILED = f"{PROBLEM_BASE_URL}/validation-failed"
    RATE_LIMITED = f"{PROBLEM_BASE_URL}/rate-limited"
    DEPENDENCY_UNAVAILABLE = f"{PROBLEM_BASE_URL}/dependency-unavailable"
    NOT_IMPLEMENTED = f"{PROBLEM_BASE_URL}/not-implemented"
    INTERNAL_ERROR = f"{PROBLEM_BASE_URL}/internal-error"


def canonical_problem_type(problem_type: Any) -> Optional[str]:
    """Normalize known legacy MLOps problem identifiers during the transition."""

    if not isinstance(problem_type, str):
        return None
    if not problem_type.startswith(f"{LEGACY_PROBLEM_BASE_URL}/"):
        return problem_type
    problem_name = problem_type.removeprefix(f"{LEGACY_PROBLEM_BASE_URL}/")
    canonical = f"{PROBLEM_BASE_URL}/{problem_name}"
    try:
        return ProblemType(canonical).value
    except ValueError:
        return problem_type


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
        self.problem_type = canonical_problem_type(problem_type)
        self.title = title
        self.detail = detail
        self.instance = instance
        self.payload = payload or {}
        self.request_id = request_id
        super().__init__(
            f"{status_code} {self.problem_type or 'about:blank'} {title}: {detail}"
        )

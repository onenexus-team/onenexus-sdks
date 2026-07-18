from enum import Enum

class AuthorizationAssigneeKind(str, Enum):
    User = "User",
    Workload = "Workload",
    ServiceClient = "ServiceClient",


from enum import Enum

class AuthorizationPolicyKind(str, Enum):
    TenantManaged = "TenantManaged",
    PlatformManaged = "PlatformManaged",


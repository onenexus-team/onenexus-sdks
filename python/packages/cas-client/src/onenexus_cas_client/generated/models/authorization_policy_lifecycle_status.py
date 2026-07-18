from enum import Enum

class AuthorizationPolicyLifecycleStatus(str, Enum):
    Draft = "Draft",
    Published = "Published",
    Archived = "Archived",


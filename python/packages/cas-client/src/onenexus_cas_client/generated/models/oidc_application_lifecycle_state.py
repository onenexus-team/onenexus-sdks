from enum import Enum

class OidcApplicationLifecycleState(str, Enum):
    Active = "Active",
    Disabled = "Disabled",
    Deleted = "Deleted",


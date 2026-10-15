from enum import Enum

class UserLifecycleState(str, Enum):
    PendingActivation = "PendingActivation",
    Invited = "Invited",
    Provisioned = "Provisioned",
    Active = "Active",
    Suspended = "Suspended",
    Deprovisioned = "Deprovisioned",
    Deleted = "Deleted",


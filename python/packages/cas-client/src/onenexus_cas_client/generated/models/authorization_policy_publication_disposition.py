from enum import Enum

class AuthorizationPolicyPublicationDisposition(str, Enum):
    Published = "Published",
    Rejected = "Rejected",
    Conflict = "Conflict",
    Unavailable = "Unavailable",


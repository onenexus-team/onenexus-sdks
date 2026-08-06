from enum import Enum

class UserKind(str, Enum):
    RootUser = "RootUser",
    Member = "Member",


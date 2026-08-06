from __future__ import annotations
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

if TYPE_CHECKING:
    from .user_kind import UserKind

@dataclass
class TenantUserSummary(Parsable):
    """
    User snapshot returned as a list item by `ListTenantUsers`.
    """
    # UTC instant when the user row was created.
    created_at: Optional[datetime.datetime] = None
    # Display name shown in UIs.
    display_name: Optional[str] = None
    # The user's email (verbatim, not normalised).
    email: Optional[str] = None
    # Whether the user has accepted the invitation and verified theirinbox. `false` for users still in the pending-invite state.
    email_confirmed: Optional[bool] = None
    # Whether this is the tenant root user or an ordinary member.
    kind: Optional[UserKind] = None
    # The user's UUID v7 primary key.
    user_id: Optional[UUID] = None
    # Canonical principal URI used by role-assignment APIs.
    user_uri: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> TenantUserSummary:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: TenantUserSummary
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return TenantUserSummary()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .user_kind import UserKind

        from .user_kind import UserKind

        fields: dict[str, Callable[[Any], None]] = {
            "createdAt": lambda n : setattr(self, 'created_at', n.get_datetime_value()),
            "displayName": lambda n : setattr(self, 'display_name', n.get_str_value()),
            "email": lambda n : setattr(self, 'email', n.get_str_value()),
            "emailConfirmed": lambda n : setattr(self, 'email_confirmed', n.get_bool_value()),
            "kind": lambda n : setattr(self, 'kind', n.get_enum_value(UserKind)),
            "userId": lambda n : setattr(self, 'user_id', n.get_uuid_value()),
            "userUri": lambda n : setattr(self, 'user_uri', n.get_str_value()),
        }
        return fields
    
    def serialize(self,writer: SerializationWriter) -> None:
        """
        Serializes information the current object
        param writer: Serialization writer to use to serialize this model
        Returns: None
        """
        if writer is None:
            raise TypeError("writer cannot be null.")
        writer.write_datetime_value("createdAt", self.created_at)
        writer.write_str_value("displayName", self.display_name)
        writer.write_str_value("email", self.email)
        writer.write_bool_value("emailConfirmed", self.email_confirmed)
        writer.write_enum_value("kind", self.kind)
        writer.write_uuid_value("userId", self.user_id)
        writer.write_str_value("userUri", self.user_uri)
    


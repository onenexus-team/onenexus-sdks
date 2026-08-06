from __future__ import annotations
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .user import User

@dataclass
class CreateUserResponse(Parsable):
    """
    Response body for `POST /api/CreateUser`.
    """
    # UTC instant after which Uri CreateUserResponse.AcceptInvitationUrl's tokenstops being honoured. Nominally `createdAt + 72 h`.
    accept_invitation_expires_at: Optional[datetime.datetime] = None
    # Fully-qualified URL the invitee clicks to land on the portal'saccept-invitation page.
    accept_invitation_url: Optional[str] = None
    # The freshly-created user.
    user: Optional[User] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> CreateUserResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: CreateUserResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return CreateUserResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .user import User

        from .user import User

        fields: dict[str, Callable[[Any], None]] = {
            "acceptInvitationExpiresAt": lambda n : setattr(self, 'accept_invitation_expires_at', n.get_datetime_value()),
            "acceptInvitationUrl": lambda n : setattr(self, 'accept_invitation_url', n.get_str_value()),
            "user": lambda n : setattr(self, 'user', n.get_object_value(User)),
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
        writer.write_datetime_value("acceptInvitationExpiresAt", self.accept_invitation_expires_at)
        writer.write_str_value("acceptInvitationUrl", self.accept_invitation_url)
        writer.write_object_value("user", self.user)
    


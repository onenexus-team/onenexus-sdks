from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

@dataclass
class AcceptInvitationRequest(Parsable):
    """
    Request body for `POST /api/AcceptInvitation`.
    """
    # Caller-generated request correlation key. Invitation-token consumptionand the resulting password/security-stamp update provide replay safety.
    client_token: Optional[str] = None
    # Initial password chosen by the user. Subject to the Identitypassword-complexity rules configured inIdentityServiceCollectionExtensions.
    password: Optional[str] = None
    # Invite token from the URL's `token` query parameter. Bound tothe user's ASP.NET Identity SecurityStamp at generate-time; verifiedvia `UserManager.VerifyUserTokenAsync`.
    token: Optional[str] = None
    # UUID of the invitee. Read from the invite URL's    `userId` query parameter by the portal.
    user_id: Optional[UUID] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AcceptInvitationRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AcceptInvitationRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AcceptInvitationRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "clientToken": lambda n : setattr(self, 'client_token', n.get_str_value()),
            "password": lambda n : setattr(self, 'password', n.get_str_value()),
            "token": lambda n : setattr(self, 'token', n.get_str_value()),
            "userId": lambda n : setattr(self, 'user_id', n.get_uuid_value()),
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
        writer.write_str_value("clientToken", self.client_token)
        writer.write_str_value("password", self.password)
        writer.write_str_value("token", self.token)
        writer.write_uuid_value("userId", self.user_id)
    


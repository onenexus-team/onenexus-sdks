from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

@dataclass
class AcceptInvitationResponse(Parsable):
    # The email property
    email: Optional[str] = None
    # The loginUrl property
    login_url: Optional[str] = None
    # The tenantId property
    tenant_id: Optional[UUID] = None
    # The userId property
    user_id: Optional[UUID] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AcceptInvitationResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AcceptInvitationResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AcceptInvitationResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "email": lambda n : setattr(self, 'email', n.get_str_value()),
            "loginUrl": lambda n : setattr(self, 'login_url', n.get_str_value()),
            "tenantId": lambda n : setattr(self, 'tenant_id', n.get_uuid_value()),
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
        writer.write_str_value("email", self.email)
        writer.write_str_value("loginUrl", self.login_url)
        writer.write_uuid_value("tenantId", self.tenant_id)
        writer.write_uuid_value("userId", self.user_id)
    


from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class CreateUserRequest(Parsable):
    """
    Request body for `POST /api/CreateUser`.
    """
    # Display name shown in UIs. 1–200 chars.
    display_name: Optional[str] = None
    # Email address. Must be a syntactically valid RFC 5322-ish address.Uniqueness is enforced per-tenant via the`(TenantId, NormalizedEmail)` composite index, not globally.
    email: Optional[str] = None
    # Caller-generated request identifier used for authorization correlation.It is not an idempotency key; per-tenant email uniqueness remains theduplicate guard for user invitations.
    request_id: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> CreateUserRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: CreateUserRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return CreateUserRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "displayName": lambda n : setattr(self, 'display_name', n.get_str_value()),
            "email": lambda n : setattr(self, 'email', n.get_str_value()),
            "requestId": lambda n : setattr(self, 'request_id', n.get_str_value()),
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
        writer.write_str_value("displayName", self.display_name)
        writer.write_str_value("email", self.email)
        writer.write_str_value("requestId", self.request_id)
    


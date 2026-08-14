from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class UpdateAuthorizationRoleDescriptionRequest(Parsable):
    """
    Request body for `POST /api/UpdateRoleDescription`.
    """
    # New human-readable description; omit or send `null` to clear it.
    description: Optional[str] = None
    # Caller-generated identifier used only to correlate the update request.
    request_id: Optional[str] = None
    # Canonical URI of the tenant role to update.
    role_uri: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> UpdateAuthorizationRoleDescriptionRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: UpdateAuthorizationRoleDescriptionRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return UpdateAuthorizationRoleDescriptionRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "description": lambda n : setattr(self, 'description', n.get_str_value()),
            "requestId": lambda n : setattr(self, 'request_id', n.get_str_value()),
            "roleUri": lambda n : setattr(self, 'role_uri', n.get_str_value()),
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
        writer.write_str_value("description", self.description)
        writer.write_str_value("requestId", self.request_id)
        writer.write_str_value("roleUri", self.role_uri)
    


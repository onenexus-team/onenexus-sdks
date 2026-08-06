from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class UpdatePolicyRequest(Parsable):
    """
    Request body for `POST /api/UpdatePolicy`.
    """
    # Optional replacement human-readable policy description. CAS stores anomitted description as an empty string.
    description: Optional[str] = None
    # Content token returned by the latest get, list, publish, or update response.
    expected_content_state_token: Optional[str] = None
    # Immutable policy name within the caller's tenant.
    name: Optional[str] = None
    # Caller-generated identifier used only to correlate the update request.
    request_id: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> UpdatePolicyRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: UpdatePolicyRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return UpdatePolicyRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "description": lambda n : setattr(self, 'description', n.get_str_value()),
            "expectedContentStateToken": lambda n : setattr(self, 'expected_content_state_token', n.get_str_value()),
            "name": lambda n : setattr(self, 'name', n.get_str_value()),
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
        writer.write_str_value("description", self.description)
        writer.write_str_value("expectedContentStateToken", self.expected_content_state_token)
        writer.write_str_value("name", self.name)
        writer.write_str_value("requestId", self.request_id)
    


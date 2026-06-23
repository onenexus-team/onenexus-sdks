from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

@dataclass
class AddServiceClientKeyRequest(Parsable):
    # The publicJwk property
    public_jwk: Optional[str] = None
    # The serviceClientId property
    service_client_id: Optional[UUID] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AddServiceClientKeyRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AddServiceClientKeyRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AddServiceClientKeyRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "publicJwk": lambda n : setattr(self, 'public_jwk', n.get_str_value()),
            "serviceClientId": lambda n : setattr(self, 'service_client_id', n.get_uuid_value()),
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
        writer.write_str_value("publicJwk", self.public_jwk)
        writer.write_uuid_value("serviceClientId", self.service_client_id)
    


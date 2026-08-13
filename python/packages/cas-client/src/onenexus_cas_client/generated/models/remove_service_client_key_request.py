from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

@dataclass
class RemoveServiceClientKeyRequest(Parsable):
    """
    Request body for `RemoveServiceClientKey`.
    """
    # Identifier of the public key to revoke.
    kid: Optional[str] = None
    # OpenIddict application id.
    service_client_id: Optional[UUID] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> RemoveServiceClientKeyRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: RemoveServiceClientKeyRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return RemoveServiceClientKeyRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "kid": lambda n : setattr(self, 'kid', n.get_str_value()),
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
        writer.write_str_value("kid", self.kid)
        writer.write_uuid_value("serviceClientId", self.service_client_id)
    


from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .service_client_dto import ServiceClientDto

@dataclass
class CreateServiceClientResponse(Parsable):
    # The serviceClient property
    service_client: Optional[ServiceClientDto] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> CreateServiceClientResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: CreateServiceClientResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return CreateServiceClientResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .service_client_dto import ServiceClientDto

        from .service_client_dto import ServiceClientDto

        fields: dict[str, Callable[[Any], None]] = {
            "serviceClient": lambda n : setattr(self, 'service_client', n.get_object_value(ServiceClientDto)),
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
        writer.write_object_value("serviceClient", self.service_client)
    


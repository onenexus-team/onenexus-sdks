from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .service_client import ServiceClient

@dataclass
class ListServiceClientsResponse(Parsable):
    """
    Response for `ListServiceClients`.
    """
    # Service clients owned by the caller's tenant.
    items: Optional[list[ServiceClient]] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ListServiceClientsResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ListServiceClientsResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ListServiceClientsResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .service_client import ServiceClient

        from .service_client import ServiceClient

        fields: dict[str, Callable[[Any], None]] = {
            "items": lambda n : setattr(self, 'items', n.get_collection_of_object_values(ServiceClient)),
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
        writer.write_collection_of_object_values("items", self.items)
    


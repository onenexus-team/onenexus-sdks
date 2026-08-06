from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .s3_role import S3Role

@dataclass
class ListS3RolesResponse(Parsable):
    """
    Response for `ListS3Roles` (the calling tenant's roles).
    """
    # The IAM roles in the calling tenant's S3 account.
    items: Optional[list[S3Role]] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ListS3RolesResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ListS3RolesResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ListS3RolesResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .s3_role import S3Role

        from .s3_role import S3Role

        fields: dict[str, Callable[[Any], None]] = {
            "items": lambda n : setattr(self, 'items', n.get_collection_of_object_values(S3Role)),
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
    


from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .json_element import JsonElement

@dataclass
class PublishPolicyRequest(Parsable):
    """
    Request body for `POST /api/PublishPolicy`.
    """
    # Optional human-readable explanation of the policy. CAS stores anomitted description as an empty string so policy read responses remainstructurally stable.
    description: Optional[str] = None
    # AWS-inspired policy object containing exactly the required,case-sensitive `Effect` (`Allow` or `Deny`),`Action`, and `ResourceScope` fields plus optional`Condition`. `Action` and `ResourceScope` accept anon-empty string or an array of at most 64 non-empty strings;`Condition` groups condition keys by operator.
    document: Optional[JsonElement] = None
    # Immutable machine-readable policy name, unique inside the caller's tenant.
    name: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> PublishPolicyRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: PublishPolicyRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return PublishPolicyRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .json_element import JsonElement

        from .json_element import JsonElement

        fields: dict[str, Callable[[Any], None]] = {
            "description": lambda n : setattr(self, 'description', n.get_str_value()),
            "document": lambda n : setattr(self, 'document', n.get_object_value(JsonElement)),
            "name": lambda n : setattr(self, 'name', n.get_str_value()),
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
        writer.write_object_value("document", self.document)
        writer.write_str_value("name", self.name)
    


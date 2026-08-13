from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class JsonElement(Parsable):
    """
    Validated policy object containing exactly the required,case-sensitive `Effect` (`Allow` or `Deny`),`Action`, and `ResourceScope` fields plus optional`Condition`. `Action` and `ResourceScope` containnormalized non-empty string arrays; `Condition` groups conditionkeys by operator.
    """
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> JsonElement:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: JsonElement
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return JsonElement()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
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
    


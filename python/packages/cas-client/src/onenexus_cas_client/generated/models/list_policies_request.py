from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class ListPoliciesRequest(Parsable):
    """
    Request body for `POST /api/ListPolicies`.
    """
    # Forward-pagination cursor. Mutually exclusive with string? ListPoliciesRequest.Before.
    after: Optional[str] = None
    # Backward-pagination cursor. Mutually exclusive with string? ListPoliciesRequest.After.
    before: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ListPoliciesRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ListPoliciesRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ListPoliciesRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "after": lambda n : setattr(self, 'after', n.get_str_value()),
            "before": lambda n : setattr(self, 'before', n.get_str_value()),
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
        writer.write_str_value("after", self.after)
        writer.write_str_value("before", self.before)
    


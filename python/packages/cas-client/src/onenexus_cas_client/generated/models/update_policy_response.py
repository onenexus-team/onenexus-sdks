from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class UpdatePolicyResponse(Parsable):
    # The diagnostics property
    diagnostics: Optional[list[str]] = None
    # The disposition property
    disposition: Optional[int] = None
    # The reasonCode property
    reason_code: Optional[str] = None
    # The stateToken property
    state_token: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> UpdatePolicyResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: UpdatePolicyResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return UpdatePolicyResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "diagnostics": lambda n : setattr(self, 'diagnostics', n.get_collection_of_primitive_values(str)),
            "disposition": lambda n : setattr(self, 'disposition', n.get_int_value()),
            "reasonCode": lambda n : setattr(self, 'reason_code', n.get_str_value()),
            "stateToken": lambda n : setattr(self, 'state_token', n.get_str_value()),
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
        writer.write_collection_of_primitive_values("diagnostics", self.diagnostics)
        writer.write_int_value("disposition", self.disposition)
        writer.write_str_value("reasonCode", self.reason_code)
        writer.write_str_value("stateToken", self.state_token)
    


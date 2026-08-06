from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_policy import AuthorizationPolicy

@dataclass
class GetPolicyResponse(Parsable):
    """
    Response body for `POST /api/GetPolicy`.
    """
    # The requested policy content.
    policy: Optional[AuthorizationPolicy] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> GetPolicyResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: GetPolicyResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return GetPolicyResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_policy import AuthorizationPolicy

        from .authorization_policy import AuthorizationPolicy

        fields: dict[str, Callable[[Any], None]] = {
            "policy": lambda n : setattr(self, 'policy', n.get_object_value(AuthorizationPolicy)),
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
        writer.write_object_value("policy", self.policy)
    


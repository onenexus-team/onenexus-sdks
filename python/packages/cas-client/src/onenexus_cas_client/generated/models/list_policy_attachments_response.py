from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_policy_attachment import AuthorizationPolicyAttachment

@dataclass
class ListPolicyAttachmentsResponse(Parsable):
    """
    Response body for policy-attachment list operations.
    """
    # Cursor for the following page, when one exists.
    after: Optional[str] = None
    # Cursor for the preceding page, when one exists.
    before: Optional[str] = None
    # Direct policy-to-role attachments matching the selected filter.
    items: Optional[list[AuthorizationPolicyAttachment]] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ListPolicyAttachmentsResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ListPolicyAttachmentsResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ListPolicyAttachmentsResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_policy_attachment import AuthorizationPolicyAttachment

        from .authorization_policy_attachment import AuthorizationPolicyAttachment

        fields: dict[str, Callable[[Any], None]] = {
            "after": lambda n : setattr(self, 'after', n.get_str_value()),
            "before": lambda n : setattr(self, 'before', n.get_str_value()),
            "items": lambda n : setattr(self, 'items', n.get_collection_of_object_values(AuthorizationPolicyAttachment)),
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
        writer.write_collection_of_object_values("items", self.items)
    


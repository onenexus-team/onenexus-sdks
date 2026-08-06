from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_role_assignment import AuthorizationRoleAssignment

@dataclass
class ListRoleAssignmentsResponse(Parsable):
    """
    Response body for `POST /api/ListRoleAssignments`.
    """
    # Cursor for the following page, when one exists.
    after: Optional[str] = None
    # Cursor for the preceding page, when one exists.
    before: Optional[str] = None
    # Direct role assignments matching the selected filter.
    items: Optional[list[AuthorizationRoleAssignment]] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ListRoleAssignmentsResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ListRoleAssignmentsResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ListRoleAssignmentsResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_role_assignment import AuthorizationRoleAssignment

        from .authorization_role_assignment import AuthorizationRoleAssignment

        fields: dict[str, Callable[[Any], None]] = {
            "after": lambda n : setattr(self, 'after', n.get_str_value()),
            "before": lambda n : setattr(self, 'before', n.get_str_value()),
            "items": lambda n : setattr(self, 'items', n.get_collection_of_object_values(AuthorizationRoleAssignment)),
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
    


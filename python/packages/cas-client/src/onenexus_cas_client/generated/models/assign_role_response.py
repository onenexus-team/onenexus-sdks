from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_role_assignment_dto import AuthorizationRoleAssignmentDto

@dataclass
class AssignRoleResponse(Parsable):
    # The assignment property
    assignment: Optional[AuthorizationRoleAssignmentDto] = None
    # The created property
    created: Optional[bool] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AssignRoleResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AssignRoleResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AssignRoleResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_role_assignment_dto import AuthorizationRoleAssignmentDto

        from .authorization_role_assignment_dto import AuthorizationRoleAssignmentDto

        fields: dict[str, Callable[[Any], None]] = {
            "assignment": lambda n : setattr(self, 'assignment', n.get_object_value(AuthorizationRoleAssignmentDto)),
            "created": lambda n : setattr(self, 'created', n.get_bool_value()),
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
        writer.write_object_value("assignment", self.assignment)
        writer.write_bool_value("created", self.created)
    


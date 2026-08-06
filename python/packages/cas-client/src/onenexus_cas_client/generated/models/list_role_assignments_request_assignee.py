from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import ComposedTypeWrapper, Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_assignee import AuthorizationAssignee
    from .list_role_assignments_request_assignee_member1 import ListRoleAssignmentsRequest_assigneeMember1

@dataclass
class ListRoleAssignmentsRequest_assignee(ComposedTypeWrapper, Parsable):
    """
    Composed type wrapper for classes AuthorizationAssignee, ListRoleAssignmentsRequest_assigneeMember1
    """
    # Composed type representation for type AuthorizationAssignee
    authorization_assignee: Optional[AuthorizationAssignee] = None
    # Composed type representation for type ListRoleAssignmentsRequest_assigneeMember1
    list_role_assignments_request_assignee_member1: Optional[ListRoleAssignmentsRequest_assigneeMember1] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ListRoleAssignmentsRequest_assignee:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ListRoleAssignmentsRequest_assignee
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        try:
            child_node = parse_node.get_child_node("")
            mapping_value = child_node.get_str_value() if child_node else None
        except AttributeError:
            mapping_value = None
        result = ListRoleAssignmentsRequest_assignee()
        if mapping_value and mapping_value.casefold() == "AuthorizationAssignee".casefold():
            from .authorization_assignee import AuthorizationAssignee

            result.authorization_assignee = AuthorizationAssignee()
        return result
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_assignee import AuthorizationAssignee
        from .list_role_assignments_request_assignee_member1 import ListRoleAssignmentsRequest_assigneeMember1

        if self.authorization_assignee:
            return self.authorization_assignee.get_field_deserializers()
        if self.list_role_assignments_request_assignee_member1:
            return self.list_role_assignments_request_assignee_member1.get_field_deserializers()
        return {}
    
    def serialize(self,writer: SerializationWriter) -> None:
        """
        Serializes information the current object
        param writer: Serialization writer to use to serialize this model
        Returns: None
        """
        if writer is None:
            raise TypeError("writer cannot be null.")
        if self.authorization_assignee:
            writer.write_object_value(None, self.authorization_assignee)
        elif self.list_role_assignments_request_assignee_member1:
            writer.write_object_value(None, self.list_role_assignments_request_assignee_member1)
    


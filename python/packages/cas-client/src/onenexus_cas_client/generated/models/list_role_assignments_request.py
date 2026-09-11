from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_assignee import AuthorizationAssignee

@dataclass
class ListRoleAssignmentsRequest(Parsable):
    """
    Request body for `POST /api/ListRoleAssignments`.
    """
    # Cursor returned by a previous response for the following page.
    after: Optional[str] = None
    # The assignee property
    assignee: Optional[AuthorizationAssignee] = None
    # Cursor returned by a previous response for the preceding page.
    before: Optional[str] = None
    # Maximum number of assignments to return, from 1 through 200.
    limit: Optional[int] = None
    # Role URI to filter by. Supply this or AuthorizationAssignee? ListRoleAssignmentsRequest.Assignee, but not both.
    role_uri: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ListRoleAssignmentsRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ListRoleAssignmentsRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ListRoleAssignmentsRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_assignee import AuthorizationAssignee

        from .authorization_assignee import AuthorizationAssignee

        fields: dict[str, Callable[[Any], None]] = {
            "after": lambda n : setattr(self, 'after', n.get_str_value()),
            "assignee": lambda n : setattr(self, 'assignee', n.get_object_value(AuthorizationAssignee)),
            "before": lambda n : setattr(self, 'before', n.get_str_value()),
            "limit": lambda n : setattr(self, 'limit', n.get_int_value()),
            "roleUri": lambda n : setattr(self, 'role_uri', n.get_str_value()),
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
        writer.write_object_value("assignee", self.assignee)
        writer.write_str_value("before", self.before)
        writer.write_int_value("limit", self.limit)
        writer.write_str_value("roleUri", self.role_uri)
    


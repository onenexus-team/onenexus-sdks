from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_assignee import AuthorizationAssignee

@dataclass
class RemoveRoleAssignmentRequest(Parsable):
    """
    Request body for `POST /api/RemoveRoleAssignment`.
    """
    # User or service client that currently has the role.
    assignee: Optional[AuthorizationAssignee] = None
    # Current assignment token returned by `ListRoleAssignments`.
    expected_state_token: Optional[str] = None
    # URI of the assigned role.
    role_uri: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> RemoveRoleAssignmentRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: RemoveRoleAssignmentRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return RemoveRoleAssignmentRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_assignee import AuthorizationAssignee

        from .authorization_assignee import AuthorizationAssignee

        fields: dict[str, Callable[[Any], None]] = {
            "assignee": lambda n : setattr(self, 'assignee', n.get_object_value(AuthorizationAssignee)),
            "expectedStateToken": lambda n : setattr(self, 'expected_state_token', n.get_str_value()),
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
        writer.write_object_value("assignee", self.assignee)
        writer.write_str_value("expectedStateToken", self.expected_state_token)
        writer.write_str_value("roleUri", self.role_uri)
    


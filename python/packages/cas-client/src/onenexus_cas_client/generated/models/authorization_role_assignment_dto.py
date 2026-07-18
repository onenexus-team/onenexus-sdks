from __future__ import annotations
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

if TYPE_CHECKING:
    from .authorization_assignee_dto import AuthorizationAssigneeDto

@dataclass
class AuthorizationRoleAssignmentDto(Parsable):
    # The assignedAtUtc property
    assigned_at_utc: Optional[datetime.datetime] = None
    # The assignedByUri property
    assigned_by_uri: Optional[str] = None
    # The assignee property
    assignee: Optional[AuthorizationAssigneeDto] = None
    # The assignmentId property
    assignment_id: Optional[UUID] = None
    # The roleUri property
    role_uri: Optional[str] = None
    # The stateToken property
    state_token: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AuthorizationRoleAssignmentDto:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AuthorizationRoleAssignmentDto
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AuthorizationRoleAssignmentDto()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_assignee_dto import AuthorizationAssigneeDto

        from .authorization_assignee_dto import AuthorizationAssigneeDto

        fields: dict[str, Callable[[Any], None]] = {
            "assignedAtUtc": lambda n : setattr(self, 'assigned_at_utc', n.get_datetime_value()),
            "assignedByUri": lambda n : setattr(self, 'assigned_by_uri', n.get_str_value()),
            "assignee": lambda n : setattr(self, 'assignee', n.get_object_value(AuthorizationAssigneeDto)),
            "assignmentId": lambda n : setattr(self, 'assignment_id', n.get_uuid_value()),
            "roleUri": lambda n : setattr(self, 'role_uri', n.get_str_value()),
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
        writer.write_datetime_value("assignedAtUtc", self.assigned_at_utc)
        writer.write_str_value("assignedByUri", self.assigned_by_uri)
        writer.write_object_value("assignee", self.assignee)
        writer.write_uuid_value("assignmentId", self.assignment_id)
        writer.write_str_value("roleUri", self.role_uri)
        writer.write_str_value("stateToken", self.state_token)
    


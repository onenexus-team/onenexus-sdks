from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

if TYPE_CHECKING:
    from .user_lifecycle_state import UserLifecycleState

@dataclass
class SuspendUserResponse(Parsable):
    """
    Response body for `POST /api/SuspendUser`.
    """
    # The member's lifecycle state after the operation.
    status: Optional[UserLifecycleState] = None
    # The target member's identifier.
    user_id: Optional[UUID] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> SuspendUserResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: SuspendUserResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return SuspendUserResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .user_lifecycle_state import UserLifecycleState

        from .user_lifecycle_state import UserLifecycleState

        fields: dict[str, Callable[[Any], None]] = {
            "status": lambda n : setattr(self, 'status', n.get_enum_value(UserLifecycleState)),
            "userId": lambda n : setattr(self, 'user_id', n.get_uuid_value()),
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
        writer.write_enum_value("status", self.status)
        writer.write_uuid_value("userId", self.user_id)
    


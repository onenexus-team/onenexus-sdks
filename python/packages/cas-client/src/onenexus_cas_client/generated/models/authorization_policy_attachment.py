from __future__ import annotations
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

if TYPE_CHECKING:
    from .authorization_policy_reference import AuthorizationPolicyReference

@dataclass
class AuthorizationPolicyAttachment(Parsable):
    """
    The created or existing direct attachment.
    """
    # When the attachment was created, in UTC.
    attached_at_utc: Optional[datetime.datetime] = None
    # URI of the principal that made the attachment.
    attached_by_uri: Optional[str] = None
    # Stable identifier of this direct policy-to-role attachment.
    attachment_id: Optional[UUID] = None
    # Policy attached to the role.
    policy: Optional[AuthorizationPolicyReference] = None
    # URI of the role that receives the policy.
    role_uri: Optional[str] = None
    # Concurrency token required to remove this attachment.
    state_token: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AuthorizationPolicyAttachment:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AuthorizationPolicyAttachment
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AuthorizationPolicyAttachment()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_policy_reference import AuthorizationPolicyReference

        from .authorization_policy_reference import AuthorizationPolicyReference

        fields: dict[str, Callable[[Any], None]] = {
            "attachedAtUtc": lambda n : setattr(self, 'attached_at_utc', n.get_datetime_value()),
            "attachedByUri": lambda n : setattr(self, 'attached_by_uri', n.get_str_value()),
            "attachmentId": lambda n : setattr(self, 'attachment_id', n.get_uuid_value()),
            "policy": lambda n : setattr(self, 'policy', n.get_object_value(AuthorizationPolicyReference)),
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
        writer.write_datetime_value("attachedAtUtc", self.attached_at_utc)
        writer.write_str_value("attachedByUri", self.attached_by_uri)
        writer.write_uuid_value("attachmentId", self.attachment_id)
        writer.write_object_value("policy", self.policy)
        writer.write_str_value("roleUri", self.role_uri)
        writer.write_str_value("stateToken", self.state_token)
    


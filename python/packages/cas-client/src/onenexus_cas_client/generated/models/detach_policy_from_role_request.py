from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_policy_reference import AuthorizationPolicyReference

@dataclass
class DetachPolicyFromRoleRequest(Parsable):
    """
    Request body for `POST /api/DetachPolicyFromRole`.
    """
    # Current attachment token returned by an attachment-list operation.
    expected_state_token: Optional[str] = None
    # Policy to detach.
    policy: Optional[AuthorizationPolicyReference] = None
    # Caller-generated identifier for safely retrying this removal.
    request_id: Optional[str] = None
    # URI of the role that currently receives the policy.
    role_uri: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> DetachPolicyFromRoleRequest:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: DetachPolicyFromRoleRequest
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return DetachPolicyFromRoleRequest()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_policy_reference import AuthorizationPolicyReference

        from .authorization_policy_reference import AuthorizationPolicyReference

        fields: dict[str, Callable[[Any], None]] = {
            "expectedStateToken": lambda n : setattr(self, 'expected_state_token', n.get_str_value()),
            "policy": lambda n : setattr(self, 'policy', n.get_object_value(AuthorizationPolicyReference)),
            "requestId": lambda n : setattr(self, 'request_id', n.get_str_value()),
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
        writer.write_str_value("expectedStateToken", self.expected_state_token)
        writer.write_object_value("policy", self.policy)
        writer.write_str_value("requestId", self.request_id)
        writer.write_str_value("roleUri", self.role_uri)
    


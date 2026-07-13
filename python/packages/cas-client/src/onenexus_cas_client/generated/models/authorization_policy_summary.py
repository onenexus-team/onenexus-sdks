from __future__ import annotations
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

@dataclass
class AuthorizationPolicySummary(Parsable):
    # The documentHash property
    document_hash: Optional[str] = None
    # The id property
    id: Optional[UUID] = None
    # The name property
    name: Optional[str] = None
    # The policyId property
    policy_id: Optional[str] = None
    # The publishedAtUtc property
    published_at_utc: Optional[datetime.datetime] = None
    # The stateToken property
    state_token: Optional[str] = None
    # The status property
    status: Optional[int] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AuthorizationPolicySummary:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AuthorizationPolicySummary
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AuthorizationPolicySummary()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "documentHash": lambda n : setattr(self, 'document_hash', n.get_str_value()),
            "id": lambda n : setattr(self, 'id', n.get_uuid_value()),
            "name": lambda n : setattr(self, 'name', n.get_str_value()),
            "policyId": lambda n : setattr(self, 'policy_id', n.get_str_value()),
            "publishedAtUtc": lambda n : setattr(self, 'published_at_utc', n.get_datetime_value()),
            "stateToken": lambda n : setattr(self, 'state_token', n.get_str_value()),
            "status": lambda n : setattr(self, 'status', n.get_int_value()),
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
        writer.write_str_value("documentHash", self.document_hash)
        writer.write_uuid_value("id", self.id)
        writer.write_str_value("name", self.name)
        writer.write_str_value("policyId", self.policy_id)
        writer.write_datetime_value("publishedAtUtc", self.published_at_utc)
        writer.write_str_value("stateToken", self.state_token)
        writer.write_int_value("status", self.status)
    


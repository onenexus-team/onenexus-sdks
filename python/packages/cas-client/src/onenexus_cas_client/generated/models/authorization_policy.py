from __future__ import annotations
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_policy_kind import AuthorizationPolicyKind
    from .authorization_policy_lifecycle_status import AuthorizationPolicyLifecycleStatus

@dataclass
class AuthorizationPolicy(Parsable):
    """
    The requested policy content.
    """
    # Optimistic concurrency token for policy content changes.
    content_state_token: Optional[str] = None
    # Canonical principal URI that originally created the policy.
    created_by_uri: Optional[str] = None
    # Human-readable policy description.
    description: Optional[str] = None
    # SHA-256 hash of the canonically normalized policy document.
    document_hash: Optional[str] = None
    # The catalogue that owns this policy.
    kind: Optional[AuthorizationPolicyKind] = None
    # Immutable machine-readable policy name.
    name: Optional[str] = None
    # UTC instant of the latest successful publication, when present.
    published_at_utc: Optional[datetime.datetime] = None
    # Current policy lifecycle state.
    status: Optional[AuthorizationPolicyLifecycleStatus] = None
    # Canonical principal URI that most recently updated the policy.
    updated_by_uri: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AuthorizationPolicy:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AuthorizationPolicy
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AuthorizationPolicy()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_policy_kind import AuthorizationPolicyKind
        from .authorization_policy_lifecycle_status import AuthorizationPolicyLifecycleStatus

        from .authorization_policy_kind import AuthorizationPolicyKind
        from .authorization_policy_lifecycle_status import AuthorizationPolicyLifecycleStatus

        fields: dict[str, Callable[[Any], None]] = {
            "contentStateToken": lambda n : setattr(self, 'content_state_token', n.get_str_value()),
            "createdByUri": lambda n : setattr(self, 'created_by_uri', n.get_str_value()),
            "description": lambda n : setattr(self, 'description', n.get_str_value()),
            "documentHash": lambda n : setattr(self, 'document_hash', n.get_str_value()),
            "kind": lambda n : setattr(self, 'kind', n.get_enum_value(AuthorizationPolicyKind)),
            "name": lambda n : setattr(self, 'name', n.get_str_value()),
            "publishedAtUtc": lambda n : setattr(self, 'published_at_utc', n.get_datetime_value()),
            "status": lambda n : setattr(self, 'status', n.get_enum_value(AuthorizationPolicyLifecycleStatus)),
            "updatedByUri": lambda n : setattr(self, 'updated_by_uri', n.get_str_value()),
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
        writer.write_str_value("contentStateToken", self.content_state_token)
        writer.write_str_value("createdByUri", self.created_by_uri)
        writer.write_str_value("description", self.description)
        writer.write_str_value("documentHash", self.document_hash)
        writer.write_enum_value("kind", self.kind)
        writer.write_str_value("name", self.name)
        writer.write_datetime_value("publishedAtUtc", self.published_at_utc)
        writer.write_enum_value("status", self.status)
        writer.write_str_value("updatedByUri", self.updated_by_uri)
    


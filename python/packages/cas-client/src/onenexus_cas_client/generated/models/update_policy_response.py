from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .authorization_policy_kind import AuthorizationPolicyKind
    from .authorization_policy_publication_disposition import AuthorizationPolicyPublicationDisposition

@dataclass
class UpdatePolicyResponse(Parsable):
    # The contentStateToken property
    content_state_token: Optional[str] = None
    # The diagnostics property
    diagnostics: Optional[list[str]] = None
    # The disposition property
    disposition: Optional[AuthorizationPolicyPublicationDisposition] = None
    # The kind property
    kind: Optional[AuthorizationPolicyKind] = None
    # The reasonCode property
    reason_code: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> UpdatePolicyResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: UpdatePolicyResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return UpdatePolicyResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .authorization_policy_kind import AuthorizationPolicyKind
        from .authorization_policy_publication_disposition import AuthorizationPolicyPublicationDisposition

        from .authorization_policy_kind import AuthorizationPolicyKind
        from .authorization_policy_publication_disposition import AuthorizationPolicyPublicationDisposition

        fields: dict[str, Callable[[Any], None]] = {
            "contentStateToken": lambda n : setattr(self, 'content_state_token', n.get_str_value()),
            "diagnostics": lambda n : setattr(self, 'diagnostics', n.get_collection_of_primitive_values(str)),
            "disposition": lambda n : setattr(self, 'disposition', n.get_enum_value(AuthorizationPolicyPublicationDisposition)),
            "kind": lambda n : setattr(self, 'kind', n.get_enum_value(AuthorizationPolicyKind)),
            "reasonCode": lambda n : setattr(self, 'reason_code', n.get_str_value()),
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
        writer.write_collection_of_primitive_values("diagnostics", self.diagnostics)
        writer.write_enum_value("disposition", self.disposition)
        writer.write_enum_value("kind", self.kind)
        writer.write_str_value("reasonCode", self.reason_code)
    


from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

if TYPE_CHECKING:
    from .oidc_application_lifecycle_state import OidcApplicationLifecycleState
    from .service_client_key import ServiceClientKey

@dataclass
class ServiceClient(Parsable):
    """
    The updated service client.
    """
    # OAuth `client_id` used at `/connect/token`.
    client_id: Optional[str] = None
    # Human-readable client name.
    display_name: Optional[str] = None
    # OpenIddict application id.
    id: Optional[UUID] = None
    # Registered public assertion keys.
    keys: Optional[list[ServiceClientKey]] = None
    # Whether the client can obtain new access tokens.
    lifecycle_state: Optional[OidcApplicationLifecycleState] = None
    # Canonical `ServiceClient` principal URI used for role assignments.
    uri: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ServiceClient:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ServiceClient
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ServiceClient()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .oidc_application_lifecycle_state import OidcApplicationLifecycleState
        from .service_client_key import ServiceClientKey

        from .oidc_application_lifecycle_state import OidcApplicationLifecycleState
        from .service_client_key import ServiceClientKey

        fields: dict[str, Callable[[Any], None]] = {
            "clientId": lambda n : setattr(self, 'client_id', n.get_str_value()),
            "displayName": lambda n : setattr(self, 'display_name', n.get_str_value()),
            "id": lambda n : setattr(self, 'id', n.get_uuid_value()),
            "keys": lambda n : setattr(self, 'keys', n.get_collection_of_object_values(ServiceClientKey)),
            "lifecycleState": lambda n : setattr(self, 'lifecycle_state', n.get_enum_value(OidcApplicationLifecycleState)),
            "uri": lambda n : setattr(self, 'uri', n.get_str_value()),
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
        writer.write_str_value("clientId", self.client_id)
        writer.write_str_value("displayName", self.display_name)
        writer.write_uuid_value("id", self.id)
        writer.write_collection_of_object_values("keys", self.keys)
        writer.write_enum_value("lifecycleState", self.lifecycle_state)
        writer.write_str_value("uri", self.uri)
    


from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union
from uuid import UUID

@dataclass
class MyTenant(Parsable):
    """
    One tenant the signed-in person can use.
    """
    # The displayName property
    display_name: Optional[str] = None
    # Whether the person is an owner there, and so can open the tenant's owner page.
    is_owner: Optional[bool] = None
    # The tenantId property
    tenant_id: Optional[UUID] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> MyTenant:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: MyTenant
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return MyTenant()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "displayName": lambda n : setattr(self, 'display_name', n.get_str_value()),
            "isOwner": lambda n : setattr(self, 'is_owner', n.get_bool_value()),
            "tenantId": lambda n : setattr(self, 'tenant_id', n.get_uuid_value()),
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
        writer.write_str_value("displayName", self.display_name)
        writer.write_bool_value("isOwner", self.is_owner)
        writer.write_uuid_value("tenantId", self.tenant_id)
    


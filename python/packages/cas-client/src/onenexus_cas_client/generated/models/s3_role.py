from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .s3_role_policy import S3RolePolicy

@dataclass
class S3Role(Parsable):
    """
    An RGW IAM role in a tenant's account.
    """
    # Role ARN (`arn:aws:iam::RGW&lt;acct&gt;:role/&lt;name&gt;`).
    arn: Optional[str] = None
    # RGW role id, if available.
    id: Optional[str] = None
    # Role name (bare, without the tenant namespace prefix).
    name: Optional[str] = None
    # Role path, if available.
    path: Optional[str] = None
    # The role's inline permission policies.
    permission_policies: Optional[list[S3RolePolicy]] = None
    # The role's trust policy (assume-role policy) JSON.
    trust_policy: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> S3Role:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: S3Role
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return S3Role()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .s3_role_policy import S3RolePolicy

        from .s3_role_policy import S3RolePolicy

        fields: dict[str, Callable[[Any], None]] = {
            "arn": lambda n : setattr(self, 'arn', n.get_str_value()),
            "id": lambda n : setattr(self, 'id', n.get_str_value()),
            "name": lambda n : setattr(self, 'name', n.get_str_value()),
            "path": lambda n : setattr(self, 'path', n.get_str_value()),
            "permissionPolicies": lambda n : setattr(self, 'permission_policies', n.get_collection_of_object_values(S3RolePolicy)),
            "trustPolicy": lambda n : setattr(self, 'trust_policy', n.get_str_value()),
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
        writer.write_str_value("arn", self.arn)
        writer.write_str_value("id", self.id)
        writer.write_str_value("name", self.name)
        writer.write_str_value("path", self.path)
        writer.write_collection_of_object_values("permissionPolicies", self.permission_policies)
        writer.write_str_value("trustPolicy", self.trust_policy)
    


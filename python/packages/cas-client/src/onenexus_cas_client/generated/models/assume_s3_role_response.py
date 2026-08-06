from __future__ import annotations
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class AssumeS3RoleResponse(Parsable):
    """
    Temporary S3 credentials returned by `AssumeS3Role`. CAS assumed therole on the caller's behalf; the caller uses these directly against S3.
    """
    # Temporary access key id.
    access_key_id: Optional[str] = None
    # UTC expiry of the temporary credentials.
    expiration: Optional[datetime.datetime] = None
    # Temporary secret access key.
    secret_access_key: Optional[str] = None
    # Session token to send with every signed S3 request.
    session_token: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> AssumeS3RoleResponse:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: AssumeS3RoleResponse
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return AssumeS3RoleResponse()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "accessKeyId": lambda n : setattr(self, 'access_key_id', n.get_str_value()),
            "expiration": lambda n : setattr(self, 'expiration', n.get_datetime_value()),
            "secretAccessKey": lambda n : setattr(self, 'secret_access_key', n.get_str_value()),
            "sessionToken": lambda n : setattr(self, 'session_token', n.get_str_value()),
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
        writer.write_str_value("accessKeyId", self.access_key_id)
        writer.write_datetime_value("expiration", self.expiration)
        writer.write_str_value("secretAccessKey", self.secret_access_key)
        writer.write_str_value("sessionToken", self.session_token)
    


from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class ServiceClientKeyDto(Parsable):
    # The alg property
    alg: Optional[str] = None
    # The crv property
    crv: Optional[str] = None
    # The kid property
    kid: Optional[str] = None
    # The kty property
    kty: Optional[str] = None
    # The publicJwk property
    public_jwk: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ServiceClientKeyDto:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ServiceClientKeyDto
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ServiceClientKeyDto()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "alg": lambda n : setattr(self, 'alg', n.get_str_value()),
            "crv": lambda n : setattr(self, 'crv', n.get_str_value()),
            "kid": lambda n : setattr(self, 'kid', n.get_str_value()),
            "kty": lambda n : setattr(self, 'kty', n.get_str_value()),
            "publicJwk": lambda n : setattr(self, 'public_jwk', n.get_str_value()),
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
        writer.write_str_value("alg", self.alg)
        writer.write_str_value("crv", self.crv)
        writer.write_str_value("kid", self.kid)
        writer.write_str_value("kty", self.kty)
        writer.write_str_value("publicJwk", self.public_jwk)
    


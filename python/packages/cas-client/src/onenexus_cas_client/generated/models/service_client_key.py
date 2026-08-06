from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class ServiceClientKey(Parsable):
    """
    A public key registered on a service client.
    """
    # JWA algorithm hint, when present (for example `ES256`).
    alg: Optional[str] = None
    # Curve name for EC keys.
    crv: Optional[str] = None
    # JWK key id used by `private_key_jwt` assertions.
    kid: Optional[str] = None
    # JWK key type (`EC` or `RSA`).
    kty: Optional[str] = None
    # The public JWK JSON persisted on the OpenIddict application.
    public_jwk: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ServiceClientKey:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ServiceClientKey
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ServiceClientKey()
    
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
    


from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.api_error import APIError
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .validation_problem_details_errors import ValidationProblemDetails_errors

@dataclass
class ValidationProblemDetails(APIError, Parsable):
    """
    Validation error response. Inspect errors for field-specific messages.
    """
    # Human-readable explanation of this occurrence.
    detail: Optional[str] = None
    # Validation messages keyed by the invalid request field.
    errors: Optional[ValidationProblemDetails_errors] = None
    # URI that identifies this error occurrence, when supplied.
    instance: Optional[str] = None
    # Short, human-readable error title.
    title: Optional[str] = None
    # Stable RFC 9457 problem type URI.
    type: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ValidationProblemDetails:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ValidationProblemDetails
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ValidationProblemDetails()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .validation_problem_details_errors import ValidationProblemDetails_errors

        from .validation_problem_details_errors import ValidationProblemDetails_errors

        fields: dict[str, Callable[[Any], None]] = {
            "detail": lambda n : setattr(self, 'detail', n.get_str_value()),
            "errors": lambda n : setattr(self, 'errors', n.get_object_value(ValidationProblemDetails_errors)),
            "instance": lambda n : setattr(self, 'instance', n.get_str_value()),
            "title": lambda n : setattr(self, 'title', n.get_str_value()),
            "type": lambda n : setattr(self, 'type', n.get_str_value()),
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
        writer.write_str_value("detail", self.detail)
        writer.write_object_value("errors", self.errors)
        writer.write_str_value("instance", self.instance)
        writer.write_str_value("title", self.title)
        writer.write_str_value("type", self.type)
    
    @property
    def primary_message(self) -> Optional[str]:
        """
        The primary error message.
        """
        return super().message


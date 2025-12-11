"""
Validation result models for form input validation.

These models represent the output of the validation agent.
"""

from typing import Any

from pydantic import BaseModel, Field


class FieldValidationError(BaseModel):
    """Validation error for a specific field."""

    field_name: str = Field(..., description="Name of the field with error")
    error_type: str = Field(..., description="Type of validation error")
    message: str = Field(..., description="Human-readable error message")
    expected: Any | None = Field(default=None, description="Expected value/format")
    received: Any | None = Field(default=None, description="Received value")


class ValidationResult(BaseModel):
    """Result of form validation."""

    is_valid: bool = Field(..., description="Whether the form data is valid")
    errors: list[FieldValidationError] = Field(
        default_factory=list, description="List of validation errors"
    )
    validated_data: dict[str, Any] | None = Field(
        default=None, description="Cleaned/validated data if valid"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-blocking warnings"
    )

    @property
    def error_count(self) -> int:
        """Get the number of validation errors."""
        return len(self.errors)

    def get_field_errors(self, field_name: str) -> list[FieldValidationError]:
        """Get all errors for a specific field."""
        return [e for e in self.errors if e.field_name == field_name]

    def to_error_dict(self) -> dict[str, list[str]]:
        """Convert errors to a dict mapping field names to error messages."""
        result: dict[str, list[str]] = {}
        for error in self.errors:
            if error.field_name not in result:
                result[error.field_name] = []
            result[error.field_name].append(error.message)
        return result


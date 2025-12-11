"""
Data models for Gen-UI system.

This module contains Pydantic models for:
- Field input (simple string-based)
- JSON Schema output (structured output)
- Validation results
"""

from gen_ui.models.field_definitions import (
    FieldAnalysisInput,
    FieldInput,
    FieldNames,
    FormInput,
)
from gen_ui.models.schema_output import (
    FormFieldSchema,
    GeneratedFormSchema,
    JSONSchemaProperty,
    UISchemaProperty,
)
from gen_ui.models.validation_result import (
    FieldValidationError,
    ValidationResult,
)

__all__ = [
    # Simple input models
    "FieldInput",
    "FieldNames",
    "FormInput",
    "FieldAnalysisInput",
    # Schema output
    "FormFieldSchema",
    "GeneratedFormSchema",
    "JSONSchemaProperty",
    "UISchemaProperty",
    # Validation
    "ValidationResult",
    "FieldValidationError",
]

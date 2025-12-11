"""
Output guardrails for Gen-UI system.

These guardrails validate the output before returning to the user.
"""

from typing import Any

from pydantic import BaseModel, Field
from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    output_guardrail,
)

from gen_ui.models.schema_output import GeneratedFormSchema


class SchemaValidationResult(BaseModel):
    """Result of schema format validation."""

    is_valid: bool = Field(..., description="Whether the schema is valid")
    errors: list[str] = Field(
        default_factory=list, description="List of validation errors"
    )
    warnings: list[str] = Field(
        default_factory=list, description="List of warnings"
    )


def _validate_json_schema(schema: dict[str, Any]) -> SchemaValidationResult:
    """Validate a JSON Schema structure."""
    errors = []
    warnings = []

    # Check required fields
    if "type" not in schema:
        errors.append("Missing 'type' field in schema")
    elif schema["type"] != "object":
        errors.append("Root schema type must be 'object'")

    if "properties" not in schema:
        errors.append("Missing 'properties' field in schema")
    elif not isinstance(schema["properties"], dict):
        errors.append("'properties' must be an object")
    elif len(schema["properties"]) == 0:
        warnings.append("Schema has no properties defined")

    # Validate properties
    if "properties" in schema and isinstance(schema["properties"], dict):
        for prop_name, prop_def in schema["properties"].items():
            if not isinstance(prop_def, dict):
                errors.append(f"Property '{prop_name}' must be an object")
                continue

            if "type" not in prop_def:
                warnings.append(f"Property '{prop_name}' has no type defined")

            # Check for valid types
            valid_types = {"string", "number", "integer", "boolean", "array", "object", "null"}
            if "type" in prop_def:
                prop_type = prop_def["type"]
                if isinstance(prop_type, str) and prop_type not in valid_types:
                    errors.append(f"Property '{prop_name}' has invalid type: {prop_type}")
                elif isinstance(prop_type, list):
                    for t in prop_type:
                        if t not in valid_types:
                            errors.append(f"Property '{prop_name}' has invalid type in array: {t}")

    # Validate required array
    if "required" in schema:
        if not isinstance(schema["required"], list):
            errors.append("'required' must be an array")
        else:
            properties = schema.get("properties", {})
            for req_field in schema["required"]:
                if req_field not in properties:
                    errors.append(f"Required field '{req_field}' not in properties")

    return SchemaValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@output_guardrail
async def schema_format_guardrail(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    output: GeneratedFormSchema,
) -> GuardrailFunctionOutput:
    """
    Guardrail to validate the generated JSON Schema format.

    Ensures the output:
    1. Has valid JSON Schema structure
    2. Contains required fields
    3. Has consistent property definitions
    4. Has valid type definitions
    """
    # Convert to JSON Schema dict
    try:
        schema_dict = output.to_json_schema()
    except Exception as e:
        return GuardrailFunctionOutput(
            output_info={
                "is_valid": False,
                "errors": [f"Failed to convert to JSON Schema: {str(e)}"],
            },
            tripwire_triggered=True,
        )

    # Validate the schema
    validation_result = _validate_json_schema(schema_dict)

    # Check UI Schema consistency - use fields list instead of properties dict
    ui_schema = output.to_ui_schema()
    ui_schema_warnings = []
    field_names = {f.name for f in output.fields}
    for field_name in ui_schema.keys():
        if field_name not in field_names:
            ui_schema_warnings.append(
                f"UI Schema has field '{field_name}' not in fields"
            )

    # Combine results
    all_warnings = validation_result.warnings + ui_schema_warnings

    return GuardrailFunctionOutput(
        output_info=SchemaValidationResult(
            is_valid=validation_result.is_valid,
            errors=validation_result.errors,
            warnings=all_warnings,
        ).model_dump(),
        tripwire_triggered=not validation_result.is_valid,
    )


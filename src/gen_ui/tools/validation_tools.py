"""
Validation tools for form data.

These tools validate user input against generated schemas.
"""

from typing import Any

from agents import Runner, function_tool, RunContextWrapper

from gen_ui.models.validation_result import ValidationResult
from gen_ui.agents.validator import create_validation_agent


@function_tool
async def validate_form_data_tool(
    ctx: RunContextWrapper[Any],
    json_schema_str: str,
    form_data_json: str,
) -> str:
    """
    Validate form data against a JSON Schema.

    This tool takes a JSON Schema and form data, validates the data,
    and returns detailed validation results with error messages.

    Args:
        json_schema_str: JSON string containing the JSON Schema.
            Example: {"type": "object", "properties": {...}, "required": [...]}
        form_data_json: JSON string containing the form data to validate.
            Example: {"email": "user@example.com", "age": 25}

    Returns:
        JSON string containing validation results:
        - is_valid: boolean indicating if data is valid
        - errors: array of validation errors with field names and messages
        - validated_data: cleaned data if valid, null if invalid
        - warnings: array of non-blocking warnings
    """
    import json

    try:
        schema = json.loads(json_schema_str)
        form_data = json.loads(form_data_json)
    except json.JSONDecodeError as e:
        return json.dumps({
            "is_valid": False,
            "errors": [{
                "field_name": "_json",
                "error_type": "parse_error",
                "message": f"Invalid JSON: {str(e)}",
            }],
            "validated_data": None,
            "warnings": [],
        })

    validator_agent = create_validation_agent()

    prompt = f"""Validate the following form data against the provided JSON Schema.

JSON Schema:
{json.dumps(schema, indent=2)}

Form Data:
{json.dumps(form_data, indent=2)}

Check each field for:
1. Type correctness
2. Required field presence
3. Format validation (email, url, date, etc.)
4. Min/max constraints
5. Pattern matching
6. Enum constraints

Provide detailed error messages for any validation failures.
If all validations pass, return the cleaned/normalized data.
"""

    result = await Runner.run(validator_agent, prompt)

    if isinstance(result.final_output, ValidationResult):
        return json.dumps(result.final_output.model_dump(), indent=2)
    else:
        return json.dumps({
            "is_valid": False,
            "errors": [{
                "field_name": "_system",
                "error_type": "validation_error",
                "message": "Validation process failed",
            }],
            "validated_data": None,
            "warnings": [str(result.final_output)],
        })


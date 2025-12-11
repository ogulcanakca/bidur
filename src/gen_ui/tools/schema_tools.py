"""
Schema generation tools.

Function tools for field analysis and schema generation.
"""

import json
from typing import Any

from agents import Runner, function_tool, RunContextWrapper

from gen_ui.agents.field_analyzer import (
    create_field_analyzer_agent,
    FieldAnalysisResult,
)
from gen_ui.agents.schema_generator import create_schema_generator_agent
from gen_ui.models.schema_output import GeneratedFormSchema


@function_tool
async def analyze_fields_tool(
    ctx: RunContextWrapper[Any],
    field_names: list[str],
    context: str | None = None,
) -> str:
    """
    Analyze field names to determine appropriate types and validation.

    Use this tool when you have a list of field names and need to
    understand what types and validation rules they should have.

    Args:
        field_names: List of field names to analyze.
            Example: ["username", "password", "email"]
        context: Optional context about the form's purpose.
            Example: "User login form"

    Returns:
        JSON string with analysis results including:
        - Inferred type for each field
        - Validation rules
        - UI widget suggestions
        - Confidence scores
    """
    analyzer = create_field_analyzer_agent()
    
    prompt = f"""Analyze these field names:

Field Names: {json.dumps(field_names)}
Context: {context or "Not provided"}

For each field, determine type, format, validation, and UI widget.
"""
    
    result = await Runner.run(analyzer, prompt)
    
    if isinstance(result.final_output, FieldAnalysisResult):
        return json.dumps(result.final_output.model_dump(), indent=2)
    else:
        return json.dumps({
            "error": True,
            "message": "Analysis failed",
            "raw": str(result.final_output),
        })


@function_tool
async def generate_form_tool(
    ctx: RunContextWrapper[Any],
    field_names: list[str],
    context: str | None = None,
    form_title: str | None = None,
) -> str:
    """
    Generate a complete form schema from field names.

    This tool analyzes field names and generates a JSON Schema
    with UI Schema that can be used with form libraries.

    Args:
        field_names: List of field names.
            Example: ["username", "password"]
        context: Optional context hint.
            Example: "Login form"
        form_title: Optional form title.
            Example: "User Login"

    Returns:
        JSON string with complete form configuration including:
        - JSON Schema
        - UI Schema
        - Form metadata
    """
    from gen_ui.orchestrator import FormGenerationOrchestrator
    
    orchestrator = FormGenerationOrchestrator()
    
    try:
        schema = await orchestrator.generate_form(
            fields=field_names,
            context=context,
            form_title=form_title,
        )
        return json.dumps(schema.to_form_config(), indent=2)
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": str(e),
        })

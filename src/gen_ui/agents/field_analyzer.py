"""
Field Analyzer Agent.

This agent analyzes field names to determine appropriate types,
validation rules, and UI configurations. It's the core "brain"
that makes Gen-UI work with just field names as input.
"""

from pydantic import BaseModel, Field
from agents import Agent

from gen_ui.agents.instructions import FIELD_ANALYZER_INSTRUCTIONS
from gen_ui.guardrails.input_guardrails import (
    safety_guardrail,
    llm_field_validation_guardrail,
)
from gen_ui.config import get_config

class InferredField(BaseModel):
    """Inferred configuration for a single field."""

    name: str = Field(..., description="Original field name")
    
    json_type: str = Field(
        ..., 
        description="JSON Schema type: string, number, integer, boolean, array, object"
    )
    format: str | None = Field(
        default=None, 
        description="JSON Schema format: email, uri, date, date-time, password, etc."
    )
    
    # UI Configuration
    title: str = Field(..., description="Human-readable label for the field")
    description: str | None = Field(default=None, description="Help text for the field")
    placeholder: str | None = Field(default=None, description="Placeholder text")
    ui_widget: str = Field(
        default="text",
        description="UI widget: text, password, email, textarea, select, checkbox, date, number, etc."
    )
    
    # Validation - explicit fields instead of dict[str, Any]
    required: bool = Field(default=True, description="Whether this field is required")
    min_length: int | None = Field(default=None, description="Minimum string length")
    max_length: int | None = Field(default=None, description="Maximum string length")
    minimum: float | None = Field(default=None, description="Minimum numeric value")
    maximum: float | None = Field(default=None, description="Maximum numeric value")
    pattern: str | None = Field(default=None, description="Regex pattern for validation")
    enum_values: list[str] | None = Field(default=None, description="Allowed values for select/enum fields")
    
    # Analysis metadata
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence score for this inference (0-1)"
    )
    reasoning: str = Field(..., description="Brief explanation of why this type was chosen")


class FieldAnalysisResult(BaseModel):
    """Complete analysis result for a list of field names."""

    fields: list[InferredField] = Field(
        ..., 
        description="Inferred configuration for each field"
    )
    form_title: str = Field(
        default="Form",
        description="Suggested form title based on fields"
    )
    form_description: str | None = Field(
        default=None,
        description="Suggested form description"
    )
    overall_context: str = Field(
        ...,
        description="Inferred context/purpose of this form"
    )


def create_field_analyzer_agent(
    model: str | None = None,
    enable_guardrails: bool = True,
    enable_llm_guardrail: bool = True,
) -> Agent[None]:
    """
    Create the Field Analyzer agent.

    This agent analyzes field names and infers appropriate
    configurations without explicit type definitions.

    Args:
        model: The OpenAI model to use. If None, uses config.default_model.
        enable_guardrails: Whether to enable input safety guardrails.

    Returns:
        Configured Agent instance.
    """
    config = get_config()
    model = model or config.default_model
    
    input_guardrails = []
    if enable_guardrails:
        input_guardrails.append(safety_guardrail)
        if enable_llm_guardrail:
            input_guardrails.append(llm_field_validation_guardrail)
    
    return Agent[None](
        name="Field Analyzer",
        instructions=FIELD_ANALYZER_INSTRUCTIONS,
        model=model,
        model_settings=config.get_model_settings(),
        output_type=FieldAnalysisResult,
        input_guardrails=input_guardrails
    )

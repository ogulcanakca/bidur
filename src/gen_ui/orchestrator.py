"""
Form Generation Orchestrator.

This is the main entry point for the Gen-UI system.
It provides a simple interface: give it field names, get back a form schema.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from agents import Agent, Runner, handoff

from gen_ui.models.schema_output import GeneratedFormSchema
from gen_ui.models.validation_result import ValidationResult
from gen_ui.agents.field_analyzer import (
    create_field_analyzer_agent,
    FieldAnalysisResult,
)
from gen_ui.agents.schema_generator import create_schema_generator_agent
from gen_ui.agents.validator import create_validation_agent
from gen_ui.tracing import setup_tracing
from gen_ui.guardrails.input_guardrails import _check_field_name
from gen_ui.config import get_config


@dataclass
class WorkflowContext:
    """Context for tracking workflow state."""
    
    field_names: list[str] = field(default_factory=list)
    context_hint: str | None = None
    analysis_result: FieldAnalysisResult | None = None
    generated_schema: GeneratedFormSchema | None = None


class FormGenerationOrchestrator:
    """
    Simple orchestrator for generating form schemas from field names.
    
    Usage:
        orchestrator = FormGenerationOrchestrator()
        
        # Generate form schema from field names
        schema = await orchestrator.generate_form(
            fields=["username", "password"],
            context="User login"
        )
        
        # Use the schema
        json_schema = schema.to_json_schema()
        ui_schema = schema.to_ui_schema()
    """

    def __init__(
        self,
        model: str | None = None,
        enable_guardrails: bool = True,
        enable_tracing: bool = True,
        trace_to_console: bool = False,
        trace_verbose: bool = False,
        trace_file: str | None = None,
        pre_validate_fields: bool = False,
    ):
        """
        Initialize the orchestrator.

        Args:
            model: OpenAI model to use for all agents. If None, uses config.default_model.
            enable_guardrails: Whether to enable input/output guardrails at agent level.
            enable_tracing: Whether to enable tracing.
            trace_to_console: Whether to print traces to console.
            trace_verbose: Whether to print detailed span information.
            trace_file: Optional file path to write traces to.
            pre_validate_fields: Whether to validate field names before API calls.
                                 If False, validation happens at agent guardrail level
                                 (visible in OpenAI logs). Default: False.
        """
        config = get_config()
        self.model = model or config.default_model
        self.enable_guardrails = enable_guardrails
        self.enable_tracing = enable_tracing
        self.pre_validate_fields = pre_validate_fields
        
        setup_tracing(
            enabled=enable_tracing,
            console=trace_to_console,
            verbose=trace_verbose,
            file_path=trace_file,
        )
        
        self._field_analyzer = create_field_analyzer_agent(
            model=model,
            enable_guardrails=enable_guardrails,
        )
        self._schema_generator = create_schema_generator_agent(
            model=model,
            enable_guardrails=enable_guardrails,
        )
        self._validator = create_validation_agent(model)

    async def generate_form(
        self,
        fields: list[str],
        context: str | None = None,
        form_title: str | None = None,
    ) -> GeneratedFormSchema:
        """
        Generate a form schema from field names.
        
        This is the main entry point. Just provide field names and
        optionally a context hint, and get back a complete form schema.

        Args:
            fields: List of field names (e.g., ["username", "password", "email"])
            context: Optional context hint (e.g., "User registration form")
            form_title: Optional form title

        Returns:
            GeneratedFormSchema with JSON Schema and UI Schema
            
        Raises:
            ValueError: If any field name is invalid (when guardrails enabled)
            
        Example:
            >>> schema = await orchestrator.generate_form(
            ...     fields=["username", "password"],
            ...     context="Login form"
            ... )
            >>> print(schema.to_json_schema())
        """
        if self.pre_validate_fields:
            invalid_fields = []
            for field_name in fields:
                is_valid, error = _check_field_name(field_name)
                if not is_valid:
                    invalid_fields.append(f"'{field_name}': {error}")
            
            if invalid_fields:
                raise ValueError(
                    f"Invalid field names detected:\n" + "\n".join(f"  - {f}" for f in invalid_fields)
                )
        
        analysis = await self.analyze_fields(fields, context)
        
        schema = await self._generate_schema_from_analysis(
            analysis=analysis,
            form_title=form_title,
        )
        
        return schema

    async def analyze_fields(
        self,
        fields: list[str],
        context: str | None = None,
    ) -> FieldAnalysisResult:
        """
        Analyze field names to infer types and validation.
        
        This is useful if you want to see the analysis before
        generating the schema, or if you want to modify it.

        Args:
            fields: List of field names
            context: Optional context hint

        Returns:
            FieldAnalysisResult with inferred configurations
        """
        prompt = self._build_analysis_prompt(fields, context)
        result = await Runner.run(self._field_analyzer, prompt)
        
        if isinstance(result.final_output, FieldAnalysisResult):
            return result.final_output
        else:
            raise ValueError(f"Unexpected output type: {type(result.final_output)}")

    async def validate_data(
        self,
        schema: GeneratedFormSchema,
        data: dict[str, Any],
    ) -> ValidationResult:
        """
        Validate form data against a generated schema.

        Args:
            schema: The generated form schema
            data: User-submitted form data

        Returns:
            ValidationResult with errors and validated data
        """ 
        prompt = f"""Validate the following form data against the JSON Schema.

JSON Schema:
{json.dumps(schema.to_json_schema(), indent=2)}

Form Data:
{json.dumps(data, indent=2)}

Check for:
1. Required fields
2. Type correctness
3. Format validation
4. Min/max constraints
5. Pattern matching

Return detailed validation results.
"""
        result = await Runner.run(self._validator, prompt)
        
        if isinstance(result.final_output, ValidationResult):
            return result.final_output
        else:
            raise ValueError(f"Unexpected output type: {type(result.final_output)}")

    async def _generate_schema_from_analysis(
        self,
        analysis: FieldAnalysisResult,
        form_title: str | None = None,
    ) -> GeneratedFormSchema:
        """Generate JSON Schema from field analysis."""
        
        fields_info = []
        for field in analysis.fields:
            field_info = {
                "name": field.name,
                "type": field.json_type,
                "title": field.title,
                "widget": field.ui_widget,
                "required": field.required,
            }
            if field.format:
                field_info["format"] = field.format
            if field.description:
                field_info["description"] = field.description
            if field.placeholder:
                field_info["placeholder"] = field.placeholder
            validation = {}
            if field.min_length is not None:
                validation["minLength"] = field.min_length
            if field.max_length is not None:
                validation["maxLength"] = field.max_length
            if field.minimum is not None:
                validation["minimum"] = field.minimum
            if field.maximum is not None:
                validation["maximum"] = field.maximum
            if field.pattern:
                validation["pattern"] = field.pattern
            if field.enum_values:
                validation["enum"] = field.enum_values
            if validation:
                field_info["validation"] = validation
            fields_info.append(field_info)
        
        prompt = f"""Generate a complete JSON Schema for this form.

Form Title: {form_title or analysis.form_title}
Form Description: {analysis.form_description or analysis.overall_context}
Form ID: generated_form

Fields:
{json.dumps(fields_info, indent=2)}

Generate:
1. JSON Schema with all properties and validation rules
2. UI Schema with widgets and placeholders
3. Required array with all required field names
"""
        
        result = await Runner.run(self._schema_generator, prompt)
        
        if isinstance(result.final_output, GeneratedFormSchema):
            return result.final_output
        else:
            raise ValueError(f"Unexpected output type: {type(result.final_output)}")

    def _build_analysis_prompt(
        self,
        fields: list[str],
        context: str | None,
    ) -> str:
        """Build prompt for field analysis."""
        prompt = f"""Analyze these field names and infer appropriate configurations:

Field Names: {json.dumps(fields)}

"""
        if context:
            prompt += f"""Context: {context}

Use this context to make better inferences about field types and validation.
"""
        else:
            prompt += """No specific context provided. Infer from field names only.
"""
        
        prompt += """
For each field, determine:
1. JSON Schema type (string, number, integer, boolean)
2. Format if applicable (email, date, password, etc.)
3. Human-readable title
4. UI widget type
5. Validation rules
6. Confidence score

Also suggest an overall form title and description based on the fields.
"""
        return prompt


async def generate_form(
    fields: list[str],
    context: str | None = None,
    model: str | None = None,
    enable_guardrails: bool = True,
    enable_tracing: bool = True,
    trace_to_console: bool = False,
    pre_validate_fields: bool = False,
) -> GeneratedFormSchema:
    """
    Convenience function to generate a form schema.
    
    Args:
        fields: List of field names
        context: Optional context hint
        model: OpenAI model to use. If None, uses config.default_model.
        enable_guardrails: Whether to enable input/output guardrails at agent level
        enable_tracing: Whether to enable tracing
        trace_to_console: Whether to print traces to console
        pre_validate_fields: Whether to validate before API calls (default: False).
                             If False, guardrails validate at agent level (visible in OpenAI logs)
        
    Returns:
        GeneratedFormSchema
        
    Example:
        >>> from gen_ui import generate_form
        >>> schema = await generate_form(["username", "password"])
        
        >>> schema = await generate_form(
        ...     ["email", "password"],
        ...     trace_to_console=True
        ... )
        
        >>> schema = await generate_form(
        ...     ["email", "password"],
        ...     pre_validate_fields=True
        ... )
    """
    orchestrator = FormGenerationOrchestrator(
        model=model,
        enable_guardrails=enable_guardrails,
        enable_tracing=enable_tracing,
        trace_to_console=trace_to_console,
        pre_validate_fields=pre_validate_fields,
    )
    return await orchestrator.generate_form(fields=fields, context=context)

"""
Gen-UI: Dynamic Form Generation with AI.

Generate form schemas from just field names. The AI analyzes
the names and creates appropriate JSON Schema + UI Schema.

Simple Usage:
    from gen_ui import generate_form
    
    schema = await generate_form(
        fields=["username", "password", "email"],
        context="User registration"
    )
    
    # Get the schemas
    json_schema = schema.to_json_schema()
    ui_schema = schema.to_ui_schema()

Advanced Usage:
    from gen_ui import FormGenerationOrchestrator
    
    orchestrator = FormGenerationOrchestrator(
        model="gpt-4o",
        enable_guardrails=True,
        enable_tracing=True,
        trace_to_console=True,  # See traces in console
    )
    
    # Analyze fields first
    analysis = await orchestrator.analyze_fields(["username", "password"])
    
    # Then generate schema
    schema = await orchestrator.generate_form(["username", "password"])
    
    # Validate user input
    result = await orchestrator.validate_data(schema, {"username": "john"})

Tracing:
    from gen_ui.tracing import setup_tracing
    
    # Enable console tracing
    setup_tracing(console=True, verbose=True)
    
    # Or write to file
    setup_tracing(file_path="traces.jsonl")
"""

from gen_ui.orchestrator import (
    FormGenerationOrchestrator,
    generate_form,
)
from gen_ui.models.field_definitions import (
    FieldInput,
    FieldNames,
    FormInput,
)
from gen_ui.models.schema_output import (
    FormFieldSchema,
    GeneratedFormSchema,
)
from gen_ui.models.validation_result import (
    ValidationResult,
    FieldValidationError,
)
from gen_ui.agents.field_analyzer import (
    FieldAnalysisResult,
    InferredField,
)
from gen_ui.tracing import (
    setup_tracing,
    disable_tracing,
    enable_tracing,
)
from gen_ui.guardrails import (
    safety_guardrail,
    llm_field_validation_guardrail,
    schema_format_guardrail,
)

__all__ = [
    # Main interface
    "FormGenerationOrchestrator",
    "generate_form",
    # Input models
    "FieldInput",
    "FieldNames",
    "FormInput",
    # Output models
    "FormFieldSchema",
    "GeneratedFormSchema",
    # Analysis
    "FieldAnalysisResult",
    "InferredField",
    # Validation
    "ValidationResult",
    "FieldValidationError",
    # Tracing
    "setup_tracing",
    "disable_tracing",
    "enable_tracing",
    # Guardrails
    "safety_guardrail",
    "llm_field_validation_guardrail",
    "schema_format_guardrail",
]

__version__ = "0.1.0"

"""
Schema Generator Agent.

This agent converts analyzed field information into JSON Schema format.
It works with the output from Field Analyzer to generate complete schemas.
"""

from agents import Agent

from gen_ui.agents.instructions import SCHEMA_GENERATOR_INSTRUCTIONS
from gen_ui.models.schema_output import GeneratedFormSchema
from gen_ui.guardrails.output_guardrails import schema_format_guardrail
from gen_ui.config import get_config


def create_schema_generator_agent(
    model: str | None = None,
    enable_guardrails: bool = True,
) -> Agent[None]:
    """
    Create the Schema Generator agent.

    This agent takes analyzed field information and produces
    a GeneratedFormSchema as structured output.

    Args:
        model: The OpenAI model to use. If None, uses config.default_model.
        enable_guardrails: Whether to enable output validation guardrails.

    Returns:
        Configured Agent instance.
    """
    config = get_config()
    model = model or config.default_model
    
    output_guardrails = [schema_format_guardrail] if enable_guardrails else []
    
    return Agent[None](
        name="Schema Generator",
        instructions=SCHEMA_GENERATOR_INSTRUCTIONS,
        model=model,
        model_settings=config.get_model_settings(),
        output_type=GeneratedFormSchema,
        output_guardrails=output_guardrails,
    )

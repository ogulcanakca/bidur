"""
Validation Agent.

This agent validates user input against the generated JSON Schema.
It provides detailed error messages and suggestions for fixing invalid input.
"""

from agents import Agent, AgentOutputSchema

from gen_ui.agents.instructions import VALIDATOR_INSTRUCTIONS
from gen_ui.models.validation_result import ValidationResult
from gen_ui.config import get_config


def create_validation_agent(model: str | None = None) -> Agent[None]:
    """
    Create the Validation agent.

    This agent validates form data against a JSON Schema and
    returns detailed validation results.

    Args:
        model: The OpenAI model to use. If None, uses config.default_model.

    Returns:
        Configured Agent instance.
    """
    config = get_config()
    model = model or config.default_model
    
    return Agent[None](
        name="Validator",
        instructions=VALIDATOR_INSTRUCTIONS,
        model=model,
        model_settings=config.get_model_settings(),
        output_type=AgentOutputSchema(ValidationResult, strict_json_schema=False),
    )


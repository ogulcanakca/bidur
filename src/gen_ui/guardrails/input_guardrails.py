"""
Input guardrails for Gen-UI system.

These guardrails validate and sanitize input before processing.
"""

import functools
import re
from typing import Any, Iterable

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
)
from pydantic import BaseModel, Field

from gen_ui.guardrails.constants import (
    JSON_ARRAY_PATTERN,
    LLM_FIELD_GUARDRAIL_INSTRUCTIONS,
    LLM_FIELD_VALIDATION_PROMPT_TEMPLATE,
    SUSPICIOUS_PATTERNS,
    VALID_FIELD_NAME,
)
from gen_ui.config import get_config


class SafetyCheckResult(BaseModel):
    """Result of input safety check."""

    is_safe: bool = Field(..., description="Whether the input is safe")
    issues: list[str] = Field(default_factory=list, description="Any issues found")


def _check_field_name(name: str) -> tuple[bool, str | None]:
    """Validate a field name."""
    if not name:
        return False, "Field name cannot be empty"
    if len(name) > 100:
        return False, "Field name too long"
    if not VALID_FIELD_NAME.match(name):
        return False, "Invalid characters in field name"
    return True, None


def _check_for_injection(text: str) -> bool:
    """Check for potential injection patterns."""
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    return True


def _is_suspicious_field(name: str) -> bool:
    """
    Identify field names that look suspicious but may pass regex.
    
    Heuristics:
    - Starts with a digit
    - Too short or too long
    - Multiple consecutive underscores or trailing underscore
    - Looks like mostly digits
    """
    if not name:
        return True
    if name[0].isdigit():
        return True
    if len(name) < 2 or len(name) > 80:
        return True
    if "__" in name or name.endswith("_"):
        return True
    if sum(ch.isdigit() for ch in name) > (len(name) * 0.6):
        return True
    return False


def _extract_field_names_from_text(text: str) -> list[str]:
    """Extract field names from the prompt text."""
    import json

    field_names: list[str] = []

    # Pattern: "Field Names: [...]"
    match = re.search(JSON_ARRAY_PATTERN, text)
    if match:
        try:
            fields_json = match.group(1)
            data = json.loads(fields_json)
            if isinstance(data, list):
                field_names.extend([str(item) for item in data if isinstance(item, str)])
        except (json.JSONDecodeError, AttributeError):
            pass

    # If empty, try parsing entire text as JSON array
    if not field_names:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                field_names.extend([str(item) for item in data if isinstance(item, str)])
        except json.JSONDecodeError:
            pass

    return field_names


@input_guardrail
async def safety_guardrail(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """
    Basic safety guardrail for input validation.
    
    Checks for:
    1. Valid field names
    2. No injection patterns
    """
    import json
    
    # Convert input to string
    if isinstance(input, list):
        text = " ".join(
            str(item.get("content", "")) if isinstance(item, dict) else str(item)
            for item in input
        )
    else:
        text = str(input)
    
    issues = []
    
    # Check for injection patterns
    if not _check_for_injection(text):
        issues.append("Potentially unsafe content detected")
    
    # Extract field names and validate with regex
    field_names = _extract_field_names_from_text(text)
    for item in field_names:
        is_valid, error = _check_field_name(item)
        if not is_valid:
            issues.append(f"Invalid field name '{item}': {error}")
    
    return GuardrailFunctionOutput(
        output_info=SafetyCheckResult(
            is_safe=len(issues) == 0,
            issues=issues,
        ).model_dump(),
        tripwire_triggered=len(issues) > 0,
    )


class LLMFieldValidationResult(BaseModel):
    """LLM-based semantic validation result."""

    issues: list[str] = Field(default_factory=list, description="Detected issues")


@functools.lru_cache(maxsize=1)
def _get_llm_field_guardrail_agent(model: str | None = None) -> Agent[None]:
    """Create (cached) LLM guardrail agent for semantic field validation."""
    config = get_config()
    model = model or config.guardrail_model
    
    return Agent[None](
        name="LLM Field Name Guardrail",
        instructions=LLM_FIELD_GUARDRAIL_INSTRUCTIONS,
        model=model,
        output_type=LLMFieldValidationResult,
    )


@input_guardrail
async def llm_field_validation_guardrail(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """
    Hybrid guardrail: regex + LLM semantic validation for field names.
    
    - Fast regex check handled by safety_guardrail.
    - Suspicious-but-regex-valid names are passed to LLM for semantic validation.
    """
    # Convert input to string
    if isinstance(input, list):
        text = " ".join(
            str(item.get("content", "")) if isinstance(item, dict) else str(item)
            for item in input
        )
    else:
        text = str(input)

    field_names = _extract_field_names_from_text(text)
    if not field_names:
        # Nothing to validate
        return GuardrailFunctionOutput(
            output_info=LLMFieldValidationResult(issues=[]).model_dump(),
            tripwire_triggered=False,
        )

    # Identify suspicious names that still passed regex
    suspicious = [name for name in field_names if _is_suspicious_field(name)]
    if not suspicious:
        return GuardrailFunctionOutput(
            output_info=LLMFieldValidationResult(issues=[]).model_dump(),
            tripwire_triggered=False,
        )

    # Ask LLM to validate suspicious names
    agent_guardrail = _get_llm_field_guardrail_agent()
    prompt = LLM_FIELD_VALIDATION_PROMPT_TEMPLATE.format(field_names=suspicious)
    result = await Runner.run(agent_guardrail, prompt)

    issues = []
    if isinstance(result.final_output, LLMFieldValidationResult):
        issues.extend(result.final_output.issues)

    return GuardrailFunctionOutput(
        output_info=LLMFieldValidationResult(issues=issues).model_dump(),
        tripwire_triggered=len(issues) > 0,
    )

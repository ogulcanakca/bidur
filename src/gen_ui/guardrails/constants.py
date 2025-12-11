"""
Constants for guardrails in Gen-UI system.

This module contains all constants, patterns, and templates used
by the guardrail system. Centralizing these makes them easier to
maintain and update.
"""

import re

# Patterns that might indicate injection attempts
SUSPICIOUS_PATTERNS = [
    r"<script",
    r"javascript:",
    r"on\w+\s*=",
    r"\{\{.*\}\}",
    r"\$\{.*\}",
    r"eval\s*\(",
    r"__proto__",
]

# Valid field name pattern (alphanumeric + underscore)
VALID_FIELD_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# JSON extraction pattern for field names
JSON_ARRAY_PATTERN = r"Field Names:\s*(\[[^\]]+\])"

# LLM Guardrail instructions for field name validation
LLM_FIELD_GUARDRAIL_INSTRUCTIONS = """You are a guardrail that validates field names for JSON Schema.
Rules:
- Field names must start with a letter or underscore.
- Allowed characters: letters, digits, underscore.
- Max length: 100 characters.
- Names that start with a digit are invalid.
- Very short (<2) or overly long (>100) names are invalid.
- Names that are mostly digits are suspicious.

Given a list of field names, return issues for any invalid names.
If all are valid, return an empty issues list.
"""

# LLM validation prompt template
LLM_FIELD_VALIDATION_PROMPT_TEMPLATE = """Validate these field names and list issues for any that are invalid.

Field Names: {field_names}

Return issues explaining which names are invalid and why. If all are valid, return an empty list.
"""


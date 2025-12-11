"""
Field definition models for dynamic form generation.

This module provides simple input models for the Gen-UI system.
The system is designed to accept just field names (strings) and
let the AI agent infer appropriate types and validation rules.
"""

from typing import Any

from pydantic import BaseModel, Field


class FieldInput(BaseModel):
    """
    Simple field input - just a name with optional hints.
    
    The AI agent will analyze the field name and context to determine
    the appropriate type, validation rules, and UI configuration.
    """
    
    name: str = Field(..., description="Field name/identifier")
    hint: str | None = Field(
        default=None, 
        description="Optional hint about what this field should contain"
    )
    required: bool = Field(
        default=True, 
        description="Whether this field is required"
    )


class FormInput(BaseModel):
    """
    Simple form input for the Gen-UI system.
    
    This is the primary input format - just provide field names
    and let the AI figure out the rest.
    """
    
    fields: list[str] = Field(
        ..., 
        description="List of field names to generate UI for"
    )
    context: str | None = Field(
        default=None,
        description="Optional context about the form's purpose (helps AI infer better types)"
    )
    form_title: str | None = Field(
        default=None,
        description="Optional title for the form"
    )


class FieldAnalysisInput(BaseModel):
    """
    Extended field input with optional hints for edge cases.
    
    Use this when you want to provide additional hints to help
    the AI make better decisions about ambiguous field names.
    """
    
    fields: list[FieldInput] = Field(
        ..., 
        description="List of field inputs with optional hints"
    )
    context: str | None = Field(
        default=None,
        description="Overall context about what these fields are for"
    )


# Type alias for simple usage
FieldNames = list[str]

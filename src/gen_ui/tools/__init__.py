"""
Function tools for Gen-UI system.

These tools can be used by agents for delegation.
"""

from gen_ui.tools.schema_tools import (
    analyze_fields_tool,
    generate_form_tool,
)
from gen_ui.tools.user_input_tool import (
    collect_user_input,
    collect_user_input_tool,
    extract_structured_output,
    run_agent_with_user_input,
)
from gen_ui.tools.validation_tools import validate_form_data_tool

__all__ = [
    "analyze_fields_tool",
    "generate_form_tool",
    "validate_form_data_tool",
    "collect_user_input",  # Core helper function
    "collect_user_input_tool",  # Function tool wrapper
    "extract_structured_output",  # Helper to extract structured output from agent result
    "run_agent_with_user_input",  # Convenience wrapper: run agent + extract output
]

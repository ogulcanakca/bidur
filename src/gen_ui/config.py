"""
Configuration module for Gen-UI system.

Handles environment variables and default settings.
"""

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv
from agents import ModelSettings

# Load environment variables
load_dotenv()


@dataclass
class GenUIConfig:
    """Configuration settings for Gen-UI."""

    # OpenAI settings
    openai_api_key: str = ""
    default_model: str = "gpt-4.1-nano-2025-04-14"
    guardrail_model: str = "gpt-4o-mini"
    
    # Model settings for deterministic behavior
    default_temperature: float = 0.0  # Deterministic output
    default_max_tokens: int | None = None

    # Form Server settings (legacy/local)
    server_port: int = 9110
    
    # MCP Server settings
    mcp_transport: str = "stdio"  # stdio or sse
    mcp_port: int = 8080
    
    # Form Server URL (for microservices architecture)
    form_server_url: str = "http://localhost:9110"

    # Guardrail settings
    enable_guardrails: bool = True
    enable_injection_check: bool = True
    enable_field_name_validation: bool = True

    # Tracing settings
    enable_tracing: bool = True
    trace_name_prefix: str = "gen-ui"

    # Output settings
    json_schema_version: str = "https://json-schema.org/draft/2020-12/schema"
    indent_json_output: int = 2
    verbose_output: bool = False
    
    def get_model_settings(self) -> ModelSettings:
        """Get ModelSettings instance with configured defaults."""
        return ModelSettings(
            temperature=self.default_temperature,
            max_tokens=self.default_max_tokens,
        )

    @classmethod
    def from_env(cls) -> "GenUIConfig":
        """
        Create configuration from environment variables.
        
        If an environment variable is not set, uses the class field default value.
        This ensures DRY principle - defaults are defined only in class fields.
        """
        _defaults = cls()
        
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", _defaults.openai_api_key),
            default_model=os.getenv("OPENAI_MODEL", _defaults.default_model),
            guardrail_model=os.getenv("GEN_UI_GUARDRAIL_MODEL", _defaults.guardrail_model),
            default_temperature=float(os.getenv("GEN_UI_TEMPERATURE", str(_defaults.default_temperature))),
            server_port=int(os.getenv("GEN_UI_SERVER_PORT", str(_defaults.server_port))),
            mcp_transport=os.getenv("MCP_TRANSPORT", _defaults.mcp_transport),
            mcp_port=int(os.getenv("MCP_PORT", str(_defaults.mcp_port))),
            form_server_url=os.getenv("FORM_SERVER_URL", _defaults.form_server_url),
            enable_guardrails=os.getenv("GEN_UI_ENABLE_GUARDRAILS", str(_defaults.enable_guardrails).lower()).lower() == "true",
            enable_injection_check=os.getenv("GEN_UI_ENABLE_INJECTION_CHECK", str(_defaults.enable_injection_check).lower()).lower() == "true",
            enable_field_name_validation=os.getenv("GEN_UI_ENABLE_FIELD_NAME_VALIDATION", str(_defaults.enable_field_name_validation).lower()).lower() == "true",
            enable_tracing=os.getenv("OPENAI_AGENTS_DISABLE_TRACING", "0" if _defaults.enable_tracing else "1") != "1",
            verbose_output=os.getenv("GEN_UI_VERBOSE_OUTPUT", str(_defaults.verbose_output).lower()).lower() == "true",
        )


config = GenUIConfig.from_env()


def get_config() -> GenUIConfig:
    """Get the current configuration."""
    return config


def update_config(**kwargs) -> GenUIConfig:
    """Update configuration settings."""
    global config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config


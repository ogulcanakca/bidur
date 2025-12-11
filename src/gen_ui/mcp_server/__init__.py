"""
MCP Server module for Gen-UI.

Provides Model Context Protocol server implementation
with stdio and SSE transport support.
"""

from gen_ui.mcp_server.server import create_mcp_server, run_mcp_server
from gen_ui.mcp_server.tools import get_mcp_tools

__all__ = [
    "create_mcp_server",
    "run_mcp_server",
    "get_mcp_tools",
]

"""
MCP Server implementation for Gen-UI.

Provides both stdio and SSE transport support for the Model Context Protocol.
"""

import asyncio
import json
import logging
from typing import Any, Literal

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from gen_ui.config import get_config
from gen_ui.mcp_server.tools import mcp_collect_user_input, get_mcp_tools
from gen_ui.mcp_server.session_store import set_session_api_key, get_session_api_key

from mcp.server.lowlevel.server import request_ctx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gen-ui-mcp")


def create_mcp_server() -> Server:
    """
    Create and configure the MCP server instance.
    
    Returns:
        Configured MCP Server with gen-ui tools registered.
    """
    server = Server("gen-ui-mcp")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        tools_def = get_mcp_tools()
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in tools_def
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        logger.info(f"Tool call: {name} with args: {arguments}")
        
        # Get session from request context for log notifications
        session = None
        try:
            ctx = request_ctx.get()
            session = ctx.session
        except LookupError:
            logger.debug("No request context available for logging")
        
        if name == "collect_user_input":
            try:
                result = await mcp_collect_user_input(
                    missing_fields=arguments.get("missing_fields", []),
                    context=arguments.get("context"),
                    timeout_seconds=arguments.get("timeout_seconds", 300),
                    session=session,  # Pass session for log notifications
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in collect_user_input: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    
    return server


async def run_stdio_server(server: Server) -> None:
    """
    Run MCP server with stdio transport.
    
    Used for Claude Desktop and local subprocess communication.
    """
    logger.info("Starting MCP server with stdio transport...")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def create_sse_app(server: Server) -> Starlette:
    """
    Create Starlette app for SSE transport.
    
    Used for remote/Docker deployment.
    """
    # SSE transport - messages endpoint is relative to SSE mount point
    sse_transport = SseServerTransport("/messages/")
    
    
    async def handle_sse(scope, receive, send):
        """Handle SSE connections - raw ASGI handler."""
        # Extract API key from headers
        headers = dict(scope.get("headers", []))
        api_key = headers.get(b"x-openai-api-key", b"").decode("utf-8")
        
        # Extract session ID from query string if available
        query_string = scope.get("query_string", b"").decode("utf-8")
        session_id = None
        for param in query_string.split("&"):
            if param.startswith("session_id="):
                session_id = param.split("=")[1]
                break
        
        if api_key:
            logger.info(f"Received API key from client (session: {session_id})")
            set_session_api_key(session_id, api_key)
        
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )
    
    async def handle_messages(scope, receive, send):
        """Handle message POST requests - raw ASGI handler."""
        await sse_transport.handle_post_message(scope, receive, send)
    
    async def health_check(request):
        """Health check endpoint."""
        config = get_config()
        return JSONResponse({
            "status": "healthy",
            "service": "gen-ui-mcp",
            "transport": "sse",
            "form_server_url": config.form_server_url,
        })
    
    from starlette.routing import Route, Mount
    
    return Starlette(
        debug=True,
        routes=[
            Route("/health", health_check, methods=["GET"]),
            Mount("/sse/messages", app=handle_messages),
            Mount("/sse", app=handle_sse),
        ],
    )


async def run_sse_server(server: Server, host: str = "0.0.0.0", port: int = 8080) -> None:
    """
    Run MCP server with SSE transport.
    
    Used for Docker/remote deployment.
    
    Args:
        server: MCP Server instance
        host: Host to bind to
        port: Port to listen on
    """
    import uvicorn
    
    logger.info(f"Starting MCP server with SSE transport on {host}:{port}...")
    
    app = create_sse_app(server)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


async def run_mcp_server(
    transport: Literal["stdio", "sse"] = "stdio",
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    """
    Run MCP server with specified transport.
    
    Args:
        transport: Transport type - "stdio" or "sse"
        host: Host for SSE transport (default: 0.0.0.0)
        port: Port for SSE transport (default: 8080)
    """
    server = create_mcp_server()
    
    if transport == "stdio":
        await run_stdio_server(server)
    elif transport == "sse":
        await run_sse_server(server, host, port)
    else:
        raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'sse'.")

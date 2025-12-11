"""
Gen-UI MCP Server Entry Point.

Run the MCP server with either stdio or SSE transport.

Usage:
    # stdio mode (for Claude Desktop)
    python run_mcp_server.py --transport stdio
    
    # SSE mode (for Docker/remote)
    python run_mcp_server.py --transport sse --port 8080
    
    # Use environment variables
    MCP_TRANSPORT=sse MCP_PORT=8080 python run_mcp_server.py
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gen_ui.config import get_config
from gen_ui.mcp_server import run_mcp_server


def main():
    """Main entry point."""
    config = get_config()
    
    parser = argparse.ArgumentParser(
        description="Gen-UI MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Claude Desktop (stdio)
  python run_mcp_server.py --transport stdio
  
  # Docker/Remote (SSE)
  python run_mcp_server.py --transport sse --port 8080
  
  # Using environment variables
  MCP_TRANSPORT=sse MCP_PORT=8080 python run_mcp_server.py

Environment Variables:
  MCP_TRANSPORT      Transport type: stdio or sse (default: stdio)
  MCP_PORT           Port for SSE transport (default: 8080)
  FORM_SERVER_URL    URL of the form server (default: http://localhost:9110)
  OPENAI_API_KEY     OpenAI API key for form generation
        """,
    )
    
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=config.mcp_transport,
        help=f"Transport type (default: {config.mcp_transport})",
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for SSE transport (default: 0.0.0.0)",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=config.mcp_port,
        help=f"Port for SSE transport (default: {config.mcp_port})",
    )
    
    args = parser.parse_args()
    
    print(f"=" * 60)
    print(f"Gen-UI MCP Server")
    print(f"=" * 60)
    print(f"Transport: {args.transport}")
    if args.transport == "sse":
        print(f"Host: {args.host}")
        print(f"Port: {args.port}")
    print(f"Form Server URL: {config.form_server_url}")
    print(f"=" * 60)
    
    try:
        asyncio.run(
            run_mcp_server(
                transport=args.transport,
                host=args.host,
                port=args.port,
            )
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

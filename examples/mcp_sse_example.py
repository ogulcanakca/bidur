#!/usr/bin/env python3
"""
MCP Server SSE Example - Docker Deployment Test

Bu örnek, Docker'da çalışan MCP Server'a SSE üzerinden bağlanır
ve collect_user_input tool'unu kullanır.

Önkoşullar:
    1. Docker container'ları çalışıyor olmalı:
       cd docker && docker-compose up -d
    
    2. Health check:
       curl http://localhost:8080/health

Kullanım:
    python examples/mcp_sse_example.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents import Agent, Runner
from agents.mcp import MCPServerSse


async def form_url_message_handler(message):
    """
    Handle MCP log notifications to display form URLs to user.
    
    This is called when the MCP server sends a log notification,
    which happens immediately when the form is created.
    """
    try:
        # Check if this is a LoggingMessageNotification
        if hasattr(message, 'root'):
            from mcp.types import LoggingMessageNotification
            if isinstance(message.root, LoggingMessageNotification):
                params = message.root.params
                data = params.data
                
                # Check if this is a form URL notification
                if isinstance(data, dict):
                    if data.get("type") == "form_url" or "form_url" in data:
                        form_url = data.get("form_url", "")
                        print("\n" + "=" * 60)
                        print("FORM URL - Please open in your browser:")
                        print("=" * 60)
                        print(f"\n   👉 {form_url}\n")
                        print("=" * 60 + "\n")
                    elif "message" in data:
                        print(f"[MCP] {data['message']}")
    except Exception as e:
        # Silently ignore parsing errors
        pass


async def main():
    """MCP Server SSE example with collect_user_input tool."""
    
    #mcp_url = "http://localhost:8080/sse"
    mcp_url = "https://gen-ui-mcp-server.onrender.com/sse"
    
    # Get OpenAI API key from environment
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    
    print("=" * 60)
    print("🚀 MCP Server SSE Example")
    print("=" * 60)
    print(f"MCP Server URL: {mcp_url}")
    print(f"OpenAI API Key: {'✅ Set' if openai_api_key else '❌ Not set'}")
    print()
    
    try:
        # Connect to MCP Server via SSE with API key in headers
        # MCPServerSse expects params dict
        async with MCPServerSse(
            params={
                "url": mcp_url,
                "headers": {"X-OpenAI-API-Key": openai_api_key} if openai_api_key else {},
            },
            client_session_timeout_seconds=300,  
            message_handler=form_url_message_handler,  
        ) as mcp_server:
            print("✅ MCP Server'a bağlanıldı!")
            
            tools = await mcp_server.list_tools()
            print(f"\nMevcut tool'lar ({len(tools)}):")
            for tool in tools:
                print(f"   - {tool.name}")
            print()
            
            # Create an agent that uses MCP tools
            agent = Agent(
                name="MCP Demo Agent",
                instructions="""
                Sen yardımcı bir asistansın.
                
                Kullanıcıdan bilgi toplamak için collect_user_input tool'unu kullan.
                Toplanan bilgileri özetle ve kullanıcıya göster.
                """,
                mcp_servers=[mcp_server],
            )
            
            result = await Runner.run(
                agent,
                "Bir form açarak benden project_name ve username, mail, birth_date bilgilerini topla."
            )
            
            print("\n" + "=" * 60)
            print("Sonuç:")
            print("=" * 60)
            print(result.final_output)
            
    except Exception as e:
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

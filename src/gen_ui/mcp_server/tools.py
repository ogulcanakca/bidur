"""
MCP Tool definitions for Gen-UI.

Wraps the collect_user_input functionality as MCP tools.
"""

import asyncio
from typing import Any, TYPE_CHECKING

from gen_ui.tools.user_input_tool import collect_user_input
from gen_ui.config import get_config

if TYPE_CHECKING:
    from mcp.server.session import ServerSession


async def mcp_collect_user_input(
    missing_fields: list[str],
    context: str | None = None,
    timeout_seconds: int = 300,
    openai_api_key: str | None = None,
    session: "ServerSession | None" = None,
) -> dict[str, Any]:
    """
    MCP-compatible wrapper for collect_user_input.
    
    This tool opens a form in the user's browser to collect missing information.
    
    Args:
        missing_fields: List of field names to collect from user.
            Examples: ["api_key", "project_name", "environment"]
        context: Optional context about why this information is needed.
            Helps generate better form labels.
        timeout_seconds: Maximum time to wait for user input (default: 300)
        openai_api_key: Optional OpenAI API key for enhanced form generation.
            If not provided, basic form will be used.
    
    Returns:
        Dictionary with user-provided values:
        {
            "api_key": "user-provided-value",
            "project_name": "my-project",
            ...
        }
    
    Raises:
        TimeoutError: If user doesn't submit within timeout
        ValueError: If missing_fields is empty
    """
    import uuid
    import logging
    import httpx
    import os
    
    from gen_ui.mcp_server.session_store import get_session_api_key
    
    config = get_config()
    logger = logging.getLogger("gen-ui-mcp")
    
    # Generate session ID
    session_id = str(uuid.uuid4()).replace("-", "")
    form_server_url = config.form_server_url or "http://localhost:9110"
    
    # Get API key: 1. SSE header (session store), 2. Tool parameter, 3. Environment
    api_key = get_session_api_key() or openai_api_key or os.environ.get("OPENAI_API_KEY")
    if api_key:
        logger.info("Using OpenAI API key for form generation")
    
    # Create form via POST API (for short URL)
    try:
        # Prepare headers with API key
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-OpenAI-API-Key"] = api_key
        
        logger.info(f"POST to Form Server: {form_server_url}/api/forms")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{form_server_url}/api/forms",
                json={
                    "session_id": session_id,
                    "fields": missing_fields,
                    "context": context,
                },
                headers=headers,
            )
            logger.info(f"Form Server response: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            short_url_path = result.get("form_url", f"/form/{session_id}")
            logger.info(f"Short URL path: {short_url_path}")
    except httpx.ConnectError as e:
        logger.error(f"Connection error to Form Server: {e}")
        short_url_path = f"/?fields={','.join(missing_fields)}&session_id={session_id}"
    except httpx.ReadTimeout as e:
        logger.error(f"Timeout connecting to Form Server: {e}")
        short_url_path = f"/?fields={','.join(missing_fields)}&session_id={session_id}"
    except Exception as e:
        logger.error(f"Failed to create form via API: {type(e).__name__}: {e}")
        short_url_path = f"/?fields={','.join(missing_fields)}&session_id={session_id}"
    
    user_facing_url = form_server_url
    if "form-server:9110" in form_server_url:
        user_facing_url = "http://localhost:9110"
    
    host_form_url = f"{user_facing_url}{short_url_path}"
    
    # Send form URL to client via log notification (shows in real-time)
    if session is not None:
        try:
            await session.send_log_message(
                level="info",
                data={
                    "type": "form_url",
                    "form_url": host_form_url,
                    "message": f"📋 Please open this form in your browser: {host_form_url}",
                },
                logger="gen-ui-form",
            )
            logger.info(f"Sent form URL notification to client: {host_form_url}")
        except Exception as e:
            logger.debug(f"Could not send log notification: {e}")
    
    print("\n" + "=" * 70)
    print("FORM URL - Open this in your browser:")
    print("=" * 70)
    print(f"\n   👉 {host_form_url}\n")
    print("=" * 70 + "\n")
    
    logger.info(f"Form URL: {host_form_url}")
    
    poll_url = f"{form_server_url}/api/submission/{session_id}"
    poll_interval = 2.0
    elapsed = 0.0
    
    logger.info(f"Polling for submission at: {poll_url}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        while elapsed < timeout_seconds:
            try:
                response = await client.get(poll_url)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("submitted"):
                        logger.info(f"Form submitted! Data: {result.get('data')}")
                        # Include form_url in output so agent can show it to user
                        return {
                            "form_url": host_form_url,
                            "message": "User successfully submitted the form",
                            "data": result.get("data", {}),
                            "_session_id": session_id,
                        }
            except Exception as e:
                logger.debug(f"Polling error (will retry): {e}")
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
    
    # Timeout - still include form_url for reference
    logger.warning(f"Form submission timed out after {timeout_seconds} seconds")
    return {
        "form_url": host_form_url,
        "error": f"Timeout waiting for form submission after {timeout_seconds} seconds",
        "_session_id": session_id,
    }


def get_mcp_tools() -> list[dict]:
    """
    Get MCP tool definitions for registration with MCP server.
    
    Returns list of tool schemas compatible with MCP protocol.
    """
    return [
        {
            "name": "collect_user_input",
            "description": """
Collect missing information from user via dynamic form UI.

WHEN TO USE:
- When you need information that wasn't provided by the user
- When you need to gather multiple related fields at once
- When user input is required to complete a task

HOW TO USE:
- Provide ALL missing fields in a SINGLE call
- Do NOT call multiple times for different fields
- Provide context to help user understand why info is needed

IMPORTANT - AFTER CALLING:
The tool returns a JSON with:
- form_url: URL the user should open to fill the form - SHOW THIS TO THE USER
- message: Status message
- data: The user-submitted form data

You MUST display the form_url to the user so they can open and fill the form.

FIELD NAMING:
- Use snake_case: api_key, project_name, user_email
- Be descriptive: server_ip_address not just ip

EXAMPLES:
- Deployment: ["api_key", "project_name", "environment"]
- User registration: ["username", "email", "password"]
- Configuration: ["database_url", "api_endpoint"]
""".strip(),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "missing_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of field names to collect from user",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional context about why this information is needed",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Maximum time to wait for user input (default: 300)",
                        "default": 300,
                    },
                    "openai_api_key": {
                        "type": "string",
                        "description": "OpenAI API key for enhanced form generation. If not provided, basic form will be used.",
                    },
                },
                "required": ["missing_fields"],
            },
        }
    ]

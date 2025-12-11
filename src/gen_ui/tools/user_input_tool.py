"""
User input collection tool.

This module provides a function tool for collecting user input via dynamic forms.
It can be used by agents when they need information from the user.

Architecture:
- collect_user_input(): Core helper function (pure logic, framework-agnostic)
- collect_user_input_tool(): Function tool wrapper (for OpenAI Agents SDK)
- Future: MCP server wrapper can use the same core helper
"""

import json
import os
import re
import socket
import subprocess
import sys
import asyncio
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

from agents import RunContextWrapper, function_tool

from gen_ui.orchestrator import FormGenerationOrchestrator
from gen_ui.config import get_config


_server_process = None  # Will be asyncio.subprocess.Process or None


def _is_server_running(port: int | None = None) -> bool:
    """Check if the Gen-UI server is actually running using fast socket check."""
    if port is None:
        config = get_config()
        port = config.server_port
    try:
        # Use socket connect for fast, non-blocking check
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)  # Very short timeout
            result = s.connect_ex(('localhost', port))
            return result == 0
    except (OSError, socket.timeout, ValueError):
        return False


def _find_project_root() -> Path:
    """
    Find the project root directory by looking for pyproject.toml.
    
    Returns:
        Path to project root directory.
    
    Raises:
        FileNotFoundError: If project root cannot be found.
    """
    current = Path(__file__).resolve()
    
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    
    for parent in current.parents:
        if (parent / "ui" / "html" / "server.py").exists():
            return parent
    
    if "src" in current.parts:
        src_index = current.parts.index("src")
        return Path(*current.parts[:src_index])
    
    raise FileNotFoundError(
        f"Could not find project root. Started from: {current}\n"
        "Make sure pyproject.toml exists in the project root."
    )


def _is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            return False
        except OSError:
            return True


async def _start_server_background(port: int | None = None, verbose: bool = False) -> bool:
    """
    Start the HTML/JS server in background if not already running.
    
    For MCP context, this function prefers to use an already-running server
    to avoid blocking subprocess operations.
    
    Returns:
        True if server was started by this function, False if it was already running.
    
    Raises:
        RuntimeError: If server is not running and cannot be started.
    """
    global _server_process
    
    if port is None:
        config = get_config()
        port = config.server_port
    
    # First, check if server is already running (non-blocking)
    if _is_server_running(port):
        if verbose:
            print(f"Form server already running on port {port}")
        return False  # Server was already running, we didn't start it
    
    # Try to start server using asyncio subprocess (non-blocking)
    project_root = _find_project_root()
    server_script = project_root / "ui" / "html" / "server.py"
    
    if not server_script.exists():
        raise FileNotFoundError(
            f"Server script not found: {server_script}\n"
            f"Project root: {project_root}\n"
            "Make sure ui/html/server.py exists."
        )
    
    if verbose:
        print(f"Starting form server on port {port}...")
    
    # Create log file
    log_file_path = project_root / ".cache" / "server.log"
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    env = os.environ.copy()
    env["GEN_UI_PROJECT_ROOT"] = str(project_root)
    
    try:
        # Windows-specific: Use subprocess.Popen with CREATE_NO_WINDOW for reliable startup
        # asyncio.create_subprocess_exec can fail in MCP stdio context on Windows
        import subprocess
        
        # Windows creation flags - only CREATE_NO_WINDOW (DETACHED_PROCESS causes CMD window)
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        # Use Popen directly for more reliable Windows startup
        process = subprocess.Popen(
            [sys.executable, str(server_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,  # Also redirect stdin to prevent any console issues
            cwd=str(project_root),
            env=env,
            creationflags=creation_flags if sys.platform == "win32" else 0,
        )
        
        # Store process reference
        _server_process = process
        
        # Wait for server to be ready using async sleep (non-blocking)
        max_wait = 10
        wait_interval = 0.3
        waited = 0.0
        
        while waited < max_wait:
            if _is_server_running(port):
                if verbose:
                    print(f"Server started successfully (waited {waited:.1f}s)")
                return True
            
            # Check if process died
            if process.poll() is not None:
                _server_process = None
                raise RuntimeError(f"Server process exited with code: {process.returncode}")
            
            # Use async sleep to not block MCP event loop
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        # Timeout - kill process
        process.terminate()
        _server_process = None
        raise RuntimeError(
            f"Server failed to start within {max_wait} seconds.\n"
            f"Check {log_file_path} for details."
        )
        
    except Exception as e:
        if verbose:
            print(f"Could not start server automatically: {e}")
            print("Please start the form server manually: python ui/html/server.py")
        raise RuntimeError(
            f"Form server not available on port {port}.\n"
            f"Please start it manually: python ui/html/server.py\n"
            f"Error: {e}"
        )


def _stop_server(verbose: bool = False) -> None:
    """
    Stop the server if we started it.
    
    Only stops the server if it was started by this module.
    External servers (started manually) are not affected.
    """
    global _server_process
    
    if _server_process is not None:
        if _server_process.returncode is None:  # Still running (async subprocess check)
            if verbose:
                print("Stopping server...")
            try:
                _server_process.terminate()
                if verbose:
                    print("Server stopped")
            except ProcessLookupError:
                pass
        _server_process = None


async def collect_user_input(
    missing_fields: list[str],
    context: str | None = None,
    timeout_seconds: int = 300,
    verbose: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Core helper function to collect user input via dynamic form UI.
    
    This is a pure logic function with no framework dependencies.
    It can be used by function tools, MCP servers, or standalone scripts.
    
    Args:
        missing_fields: List of field names that need user input.
            Example: ["username", "password", "email"]
        context: Optional context about why this information is needed.
            Example: "User login credentials"
        timeout_seconds: Maximum time to wait for user input (default: 300)
        verbose: Whether to print progress messages (default: True)
    
    Returns:
        Dictionary with user-provided values:
        {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com"
        }
    
    Raises:
        TimeoutError: If user doesn't submit within timeout_seconds
        ValueError: If missing_fields is empty or invalid
    
    Example:
        >>> result = await collect_user_input(
        ...     missing_fields=["username", "password"],
        ...     context="Login credentials"
        ... )
        >>> print(result["username"])
    """
    if not missing_fields:
        raise ValueError("missing_fields cannot be empty")
    
    # Use provided session_id or generate new one
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    server_started_by_us = False
    
    fields_param = ",".join(missing_fields)
    
    try:
        config = get_config()
        server_port = config.server_port
        
        try:
            server_started_by_us = await _start_server_background(port=server_port, verbose=verbose)
            if verbose:
                print("Server started automatically (or already running)")
        except Exception as e:
            server_started_by_us = False  # Server başlatılamadı
            if verbose:
                print(f"Warning: Could not start server automatically: {e}")
                print("   Make sure server is running manually: python ui/html/server.py")
        
        url = f"http://localhost:{server_port}/?fields={fields_param}&session_id={session_id}"
        if verbose:
            print(f"\nOpening HTML/JS form in browser...")
            print(f"   Session ID: {session_id}")
        
        if context:
            url += f"&context={urllib.parse.quote(context)}"
        
        if verbose:
            print(f"   URL: {url}")
        
        webbrowser.open(url)
        
        # NOTE: Removed generate_form call here - it was causing 50+ second delays
        # due to OpenAI rate limits, which blocked the MCP event loop and caused timeouts.
        # Form Server now renders simple fields directly without AI generation.
        
        if verbose:
            print(f"\nForm opened with fields: {missing_fields}")
            print("\\nForm opened! Waiting for user input...")
            print(f"\\nWaiting for form submission (timeout: {timeout_seconds}s)...")
            print("   Fill out the form in the browser and click Submit.")
        
        project_root = _find_project_root()
        
        if verbose:
            print(f"[DEBUG] Client project root: {project_root}", file=sys.stderr, flush=True)
            print(f"[DEBUG] pyproject.toml exists: {(project_root / 'pyproject.toml').exists()}", file=sys.stderr, flush=True)
        
        cache_dir = project_root / ".cache" / "submissions"
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_file = cache_dir / f"{session_id}_submission.json"
        
        if verbose:
            print(f"   Waiting for submission file: {output_file}")
        
        check_interval = 0.5
        elapsed_time = 0
        last_size = 0
        stable_count = 0
        last_printed_time = -1  # Track last printed time to avoid duplicates
        
        while elapsed_time < timeout_seconds:
            if output_file.exists():
                try:
                    current_size = output_file.stat().st_size
                    
                    if current_size != last_size:
                        last_size = current_size
                        stable_count = 0
                    else:
                        stable_count += 1
                    
                    if stable_count >= 2 and current_size > 0:
                        max_read_retries = 3
                        for retry in range(max_read_retries):
                            try:
                                with open(output_file, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    if not content.strip():
                                        if retry < max_read_retries - 1:
                                            await asyncio.sleep(0.2)
                                            continue
                                        else:
                                            raise ValueError("File is empty")
                                    
                                    structured_output = json.loads(content)
                                
                                structured_output.pop("_session_id", None)
                                
                                if verbose:
                                    print(f"\nForm submitted! Received structured output:")
                                    print("=" * 60)
                                    print(json.dumps(structured_output, indent=2))
                                    print("=" * 60)
                                    print(f"   Saved to: {output_file}")
                                
                                return structured_output
                                
                            except json.JSONDecodeError as e:
                                if retry < max_read_retries - 1:
                                    await asyncio.sleep(0.2)
                                    continue
                                else:
                                    if verbose:
                                        print(f"\nError reading output file after {max_read_retries} retries: {e}")
                                    break   
                            except Exception as e:
                                if retry < max_read_retries - 1:
                                    await asyncio.sleep(0.2)
                                    continue
                                else:
                                    if verbose:
                                        print(f"\nError reading file: {e}")
                                    break
                    
                except (OSError, PermissionError) as e:
                    if verbose and elapsed_time % 5 == 0:
                        print(f"File locked, retrying... ({elapsed_time}s elapsed)")
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
                    continue
                except Exception as e:
                    if verbose:
                        print(f"\nUnexpected error: {e}")
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
                    continue
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
            
            # Print status every 10 seconds (only once per 10-second interval)
            current_second = int(elapsed_time)
            if verbose and current_second % 10 == 0 and current_second > 0 and current_second != last_printed_time:
                print(f"Still waiting... ({current_second}s elapsed)")
                last_printed_time = current_second
        
        if verbose:
            print(f"\nTimeout reached ({timeout_seconds}s). No submission received.")
            print("The form is still open - you can submit and check the file manually.")
        
        raise TimeoutError(
            f"User input collection timed out after {timeout_seconds} seconds. "
            f"Form is still open at {url}"
        )
    
    finally:
        # Cleanup: Stop server only if we started it
        if server_started_by_us:
            _stop_server(verbose=verbose)


@function_tool
async def collect_user_input_tool(
    ctx: RunContextWrapper[Any],
    missing_fields: list[str],
    context: str | None = None,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """
    Collect missing information from user via dynamic form UI.
    
    FIELD NAME NORMALIZATION:
    - Convert user descriptions to snake_case automatically
    - Examples:
      * "API key" → "api_key"
      * "Project name" → "project_name"  
      * "Server IP address" → "server_ip_address"
      * "Port number" → "port_number"
    - Use lowercase with underscores, remove spaces and special characters
    - The system will handle conversion, but using proper format helps
    
    WHEN TO USE THIS TOOL:
    - When you detect missing required information that prevents task completion
    - When you need to gather multiple related fields from the user at once
    - When user input is essential to proceed with the current task
    - When the initial request or context doesn't contain all necessary information
    
    HOW TO USE THIS TOOL:
    - CRITICAL: Always provide ALL missing fields in a SINGLE call
    - Do NOT call this tool multiple times - collect everything in one form
    - If the user/prompt lists multiple fields (e.g., 5, 10, 13 fields), 
      you MUST include ALL of them in the missing_fields list
    - Identify all missing fields first, then call once with the complete list
    - Provide context to help the user understand why this information is needed
    - Example: If prompt says "I need: field1, field2, field3, field4, field5",
      then missing_fields must be ["field1", "field2", "field3", "field4", "field5"]
    
    WHY THIS TOOL:
    - Opens a user-friendly form UI in the browser
    - Validates user input automatically
    - Returns structured data ready for use
    - More efficient than asking for fields one by one
    
    Args:
        missing_fields: List of ALL field names that need user input.
            CRITICAL: Include ALL missing fields in ONE list.
            Example (3 fields): ["api_key", "project_name", "environment"]
            Example (13 fields): ["api_key", "project_name", "environment", 
                                  "port_number", "server_name", "server_ip", 
                                  "server_os", "server_cpu", "server_memory",
                                  "server_disk_space", "server_disk_type", 
                                  "server_disk_size", "server_disk_speed"]
            WRONG: ["api_key"], then ["project_name"], then ["environment"]
            RIGHT: ALL fields in ONE list: ["api_key", "project_name", "environment", ...]
        context: Optional context about why this information is needed.
            Helps the AI generate better form labels and descriptions.
            Example: "Application deployment configuration"
        timeout_seconds: Maximum time to wait for user input (default: 300)
    
    Returns:
        Dictionary with user-provided values:
        {
            "api_key": "sk-...",
            "project_name": "my-app",
            "environment": "production"
        }
    
    Example scenarios:
        1. Deployment task missing credentials:
           missing_fields=["api_key", "project_name", "environment"]
           context="Application deployment configuration"
        
        2. User registration missing details:
           missing_fields=["email", "password", "username"]
           context="User account creation"
        
        3. Configuration setup:
           missing_fields=["database_url", "api_endpoint", "secret_key"]
           context="Application configuration"
    
    Best practices:
        - Always collect all related fields together
        - Provide meaningful context for better UX
        - Use descriptive field names (e.g., "api_key" not "key")
        - Wait for the tool to return before proceeding
    """
    config = get_config()
    return await collect_user_input(
        missing_fields=missing_fields,
        context=context,
        timeout_seconds=timeout_seconds,
        verbose=config.verbose_output,
    )


def extract_structured_output(result: Any) -> dict[str, Any]:
    """
    Extract structured output from agent result.
    
    When using tool_use_behavior="stop_on_first_tool", the SDK may return
    tool output as a string instead of a dict. This helper function handles
    both cases and always returns a dict.
    
    Args:
        result: Agent result object with final_output attribute
        
    Returns:
        Dictionary with structured data (always a dict, never a string)
        
    Example:
        >>> from agents import Agent, Runner
        >>> from gen_ui.tools.user_input_tool import collect_user_input_tool, extract_structured_output
        >>> 
        >>> agent = Agent(
        ...     name="My Agent",
        ...     tools=[collect_user_input_tool],
        ...     tool_use_behavior="stop_on_first_tool"
        ... )
        >>> result = await Runner.run(agent, "Collect user info")
        >>> data = extract_structured_output(result)  # Always returns dict
    """
    import json
    import ast
    
    final_output = result.final_output if hasattr(result, 'final_output') else result
    
    # Handle both dict and string outputs
    if isinstance(final_output, dict):
        return final_output
    elif isinstance(final_output, str):
        # Try to parse if it's a JSON string first
        try:
            return json.loads(final_output)
        except json.JSONDecodeError:
            # If not JSON, it might be a Python dict string representation
            try:
                return ast.literal_eval(final_output)
            except (ValueError, SyntaxError):
                # If parsing fails, return as-is wrapped in dict
                return {"raw_output": final_output}
    else:
        # For other types, try to convert to dict
        return {"output": final_output}


async def run_agent_with_user_input(
    agent: Any,
    prompt: str,
    *,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Run an agent and automatically extract structured output from user input tool.
    
    This is a convenience wrapper that:
    1. Runs the agent with the given prompt
    2. Automatically extracts structured output (handles both dict and string)
    3. Returns a clean dict (never a string)
    
    Use this when your agent uses collect_user_input_tool and you want
    the structured output directly without manual parsing.
    
    Args:
        agent: Agent instance (must have collect_user_input_tool in tools)
        prompt: Prompt to send to the agent
        verbose: Whether to print the structured output (default: True)
        
    Returns:
        Dictionary with structured data (always a dict, never a string)
        
    Example:
        >>> from agents import Agent
        >>> from gen_ui.tools import collect_user_input_tool, run_agent_with_user_input
        >>> 
        >>> agent = Agent(
        ...     name="My Agent",
        ...     tools=[collect_user_input_tool],
        ...     tool_use_behavior="stop_on_first_tool"
        ... )
        >>> data = await run_agent_with_user_input(
        ...     agent,
        ...     "Collect API key and project name from user"
        ... )
        >>> print(data["api_key"])  # Direct access, no parsing needed
    """
    from agents import Runner
    import json
    
    result = await Runner.run(agent, prompt)
    output_data = extract_structured_output(result)
    
    if verbose:
        print(f"\n✅ Collected structured data:")
        print("=" * 60)
        print(json.dumps(output_data, indent=2))
        print("=" * 60)
    
    return output_data


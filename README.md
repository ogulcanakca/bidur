# bidur

> Bi dur, some info is missing! Let me generate UI to gather the missing pieces. 

Dynamic form generation for AI agents via Model Context Protocol (MCP).

<p align="center">
  <img src="./assets/bidur.png" alt="bi-dur" width="1000">
</p>

## Live Demo

**[Try bidur Demo →](https://bidur-demo-latest.onrender.com)**

## What It Does

```
Agent: "I need api_key, project_name from the user"
       ↓
MCP Server creates a form → User fills it in browser → Data returns to agent
```

## Quick Start

### Option 1: Remote SSE (Recommended for Testing)

```python
from agents import Agent, Runner
from agents.mcp import MCPServerSse

async def main():
    async with MCPServerSse(
        params={
            "url": "https://gen-ui-mcp-server.onrender.com/sse",
            "headers": {"X-OpenAI-API-Key": "sk-..."},
        },
        client_session_timeout_seconds=300,
    ) as mcp_server:
        
        agent = Agent(
            name="My Agent",
            instructions="Use collect_user_input to gather info from user.",
            mcp_servers=[mcp_server],
        )
        
        result = await Runner.run(agent, "Collect user's name and email")
```

### Option 2: Docker (Local Development)

```bash
cd docker
docker-compose up -d

# MCP Server: http://localhost:8080
# Form Server: http://localhost:9110
```

Then test with MCP Inspector:
```bash
npx @modelcontextprotocol/inspector
```
Set URL to `http://localhost:8080/sse` in browser UI. Add a new Custom Header named X-OpenAI-API-Key. Enter your OpenAI API key in the Value field.

### Option 3: Remote SSE with MCP Inspector

```bash
npx @modelcontextprotocol/inspector sse https://gen-ui-mcp-server.onrender.com/sse --header "X-OpenAI-API-Key: sk-..."
```

Then in the browser UI:
1. Set URL to: `https://gen-ui-mcp-server.onrender.com/sse`
2. Go to **Tools** tab
3. Run `collect_user_input` with test input
4. Check **Server Notifications** for form URL

## Testing

```bash
python examples/mcp_sse_example.py
```

## Installation

```bash
git clone https://github.com/ogulcanakca/bidur.git
cd bidur
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...
```

## Available Tool

### `collect_user_input`

| Parameter | Type | Description |
|-----------|------|-------------|
| `missing_fields` | `list[str]` | Field names to collect (e.g., `["username", "email"]`) |
| `context` | `str` | Optional context for better form generation |
| `timeout_seconds` | `int` | Max wait time (default: 300) |

**Returns:**
```json
{
  "form_url": "https://...",
  "message": "User successfully submitted the form",
  "data": {"username": "john", "email": "john@example.com"}
}
```

## Architecture

```
┌─────────────┐     SSE      ┌─────────────┐     HTTP     ┌─────────────┐
│   Agent     │◄────────────►│ MCP Server  │◄────────────►│ Form Server │
│ (Your App)  │              │  Port 8080  │              │  Port 9110  │
└─────────────┘              └─────────────┘              └─────────────┘
                                    │                            │
                              Tool Handler                  HTML/JS Form
                              API Key Mgmt                  Schema Gen
```

## Project Structure

```
gen-ui-mcp/
├── src/gen_ui/
│   ├── mcp_server/          # MCP Server implementation
│   │   ├── server.py        # SSE transport, tool routing
│   │   └── tools.py         # collect_user_input tool
│   ├── agents/              # Form schema generation
│   └── tools/               # Standalone tool (non-MCP)
├── ui/html/
│   ├── server.py            # Form Server HTTP API
│   └── index.html           # Form UI
├── docker/
│   ├── Dockerfile.mcp
│   ├── Dockerfile.form
│   └── docker-compose.yml
├── examples/
│   └── mcp_sse_example.py   # SSE connection example
└── run_mcp_server.py        # Entry point (stdio/sse)
```

## Notes

### Client Limitations

> **Research in Progress:** VS Code, Cursor, and Claude Desktop clients do not currently display log notifications during tool execution. This means the form URL is not visible until after form submission. Investigation is ongoing for alternative approaches.

### OpenAI Agents SDK Features

This project supports [Guardrails](https://openai.github.io/openai-agents-python/guardrails/) and [Tracing](https://openai.github.io/openai-agents-python/tracing/) features from the OpenAI Agents SDK.

**Built-in Guardrails:**

| Guardrail | Type | Description |
|-----------|------|-------------|
| `safety_guardrail` | Input | Validates field names, checks for injection patterns |
| `llm_field_validation_guardrail` | Input | LLM-based semantic validation for suspicious field names |
| `schema_format_guardrail` | Output | Validates JSON Schema structure and property definitions |

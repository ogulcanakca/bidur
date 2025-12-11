# Global session store for MCP connections

# Store API keys by session
# Key: session_id or "_latest", Value: OpenAI API key
session_api_keys: dict[str, str] = {}


def get_session_api_key(session_id: str | None = None) -> str | None:
    """Get the API key for a session, or the latest if session_id is None."""
    if session_id and session_id in session_api_keys:
        return session_api_keys[session_id]
    return session_api_keys.get("_latest")


def set_session_api_key(session_id: str | None, api_key: str) -> None:
    """Store an API key for a session."""
    if session_id:
        session_api_keys[session_id] = api_key
    session_api_keys["_latest"] = api_key

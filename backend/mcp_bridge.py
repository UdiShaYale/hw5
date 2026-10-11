"""Direct MCP access for the FastAPI routes.

Some routes need shop facts without running an agent — listing tickets, reading
the balance, recording a payment a human just approved. They still go through
the MCP server rather than opening SQLite, so there is exactly one shop-tools
layer in this project.

The difference from agents/shop_mcp.py is only the caller: that module hands the
tools to PydanticAI, this one calls them from a request handler. Same server,
same database, same guard rails inside the tools.

One stdio client is opened for the app's lifetime (spawning a subprocess per
request would be slow) and serialised with a lock, since the connection is not
safe to share across concurrent calls.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import Client

SERVER_SCRIPT = Path(__file__).resolve().parents[1] / "mcp_server" / "mcp_server.py"

_client: Client | None = None
_lock = asyncio.Lock()


async def connect() -> None:
    """Open the shared MCP connection. Called from the FastAPI lifespan."""
    global _client
    if _client is None:
        _client = Client(SERVER_SCRIPT)
        await _client.__aenter__()


async def disconnect() -> None:
    global _client
    if _client is not None:
        await _client.__aexit__(None, None, None)
        _client = None


async def call(tool: str, **args: Any) -> Any:
    """Call one MCP tool and return its parsed result."""
    if _client is None:
        raise RuntimeError("MCP client is not connected.")
    async with _lock:
        result = await _client.call_tool(tool, args)
    return result.data


async def list_tool_names() -> list[str]:
    if _client is None:
        raise RuntimeError("MCP client is not connected.")
    async with _lock:
        tools = await _client.list_tools()
    return sorted(t.name for t in tools)

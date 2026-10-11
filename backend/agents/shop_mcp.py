"""The one and only shop-tools layer: the Campus Customs MCP server.

Every agent gets its tools from here. There is no second data path — no direct
sqlite3 access anywhere in backend/ — so a fact only reaches an agent if an MCP
tool returned it.

build_shop_toolset() wraps mcp_server/mcp_server.py over stdio and installs a
process_tool_call hook that:
  * writes every MCP call and its result into output/audit_trail.json, and
  * enforces the per-run tool-call ceiling from config.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset, ToolResult

from agents.config import MAX_TOOL_CALLS_PER_RUN

SERVER_SCRIPT = Path(__file__).resolve().parents[2] / "mcp_server" / "mcp_server.py"

# Tools that move money or change shop state. The team may only call these when
# the run was started with spending approved; see prompts and TeamDeps.
WRITE_TOOLS = {
    "record_payment",
    "adjust_inventory_qty",
    "update_ticket_status",
    "append_desk_note",
}
MONEY_TOOLS = {"record_payment"}


def _clip(value: Any, limit: int = 1200) -> Any:
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= limit else text[:limit] + f"… (+{len(text) - limit} chars)"


async def _audited_call(
    ctx: RunContext[Any],
    call_tool: CallToolFunc,
    name: str,
    args: dict[str, Any],
) -> ToolResult:
    """Log every MCP tool call to the audit trail and apply the run's limits."""
    deps = ctx.deps
    state = deps.state

    if state.tool_calls >= MAX_TOOL_CALLS_PER_RUN:
        refusal = f"Tool-call budget for this run is exhausted ({MAX_TOOL_CALLS_PER_RUN}). Report what you have."
        deps.emit("mcp_tool_call", tool=name, args=args, blocked=refusal)
        return {"ok": False, "error": refusal}

    # A money tool is never allowed to fire on an unapproved run, whatever the
    # model was talked into. The MCP server also demands approved_by; this is
    # the second lock, on the client side.
    if name in MONEY_TOOLS and not deps.allow_spending:
        refusal = (
            "Blocked: this run was not started with spending approved. "
            "Recommend the payment and set the ticket to needs_human instead."
        )
        deps.emit("mcp_tool_call", tool=name, args=args, blocked=refusal)
        return {"ok": False, "error": refusal}

    state.tool_calls += 1
    result = await call_tool(name, args)
    deps.emit(
        "mcp_tool_call",
        tool=name,
        args=args,
        is_write=name in WRITE_TOOLS,
        result=_clip(result),
        tool_calls_used=state.tool_calls,
    )
    return result


def build_shop_toolset() -> MCPToolset:
    """Connect to the Campus Customs MCP server over stdio."""
    if not SERVER_SCRIPT.exists():
        raise RuntimeError(f"MCP server script not found: {SERVER_SCRIPT}")
    return MCPToolset(
        SERVER_SCRIPT,
        id="campus-customs",
        process_tool_call=_audited_call,
    )

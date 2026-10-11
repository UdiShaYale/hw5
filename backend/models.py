"""Shared data types for the Campus Customs agent team.

Nothing here holds shop data. Shop facts (inventory, pricing, leases, invoices,
cash) live only in the MCP server over data/campus_customs_new.db. These models
describe the *team* — who the agents are, how work is delegated between them,
and what one agent-loop step looks like in the audit trail.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentKey = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_ROSTER: list[dict] = [
    {
        "key": "boss",
        "name": "Shop Boss",
        "title": "Owner on duty",
        "accent": "#1d4ed8",
        "remit": (
            "Owns the ticket queue. Triages each open ticket, delegates to the right "
            "specialist, resolves conflicts between them, and writes the final plan."
        ),
    },
    {
        "key": "inventory",
        "name": "Inventory",
        "title": "Stock and restock",
        "accent": "#2563eb",
        "remit": (
            "On-hand counts by (sku, size), what a size run looks like, which vendor "
            "could reprint a shortfall and how many days that takes."
        ),
    },
    {
        "key": "accounting",
        "name": "Accounting",
        "title": "Cash, invoices, margin",
        "accent": "#0ea5e9",
        "remit": (
            "Cash position, vendor invoices, the payments ledger, and whether a "
            "proposed discount still clears unit cost."
        ),
    },
    {
        "key": "facilities",
        "name": "Facilities",
        "title": "Lease and premises",
        "accent": "#3b82f6",
        "remit": (
            "Lease terms, rent amounts and due dates, and verifying what a landlord "
            "notice claims against the signed lease."
        ),
    },
    {
        "key": "customer_service",
        "name": "Customer Service",
        "title": "Customer-facing replies",
        "accent": "#60a5fa",
        "remit": (
            "Drafts what the customer is actually told, and moves tickets to their "
            "final status once the specialists have reported."
        ),
    },
]

AGENTS_BY_KEY = {a["key"]: a for a in AGENT_ROSTER}
AGENT_NAMES = {a["key"]: a["name"] for a in AGENT_ROSTER}
SPECIALIST_KEYS = [a["key"] for a in AGENT_ROSTER if a["key"] != "boss"]


class Delegation(BaseModel):
    """One agent asking another agent to do something."""

    from_agent: str
    to_agent: str
    agent_key: str
    question: str
    reply: str = ""
    depth: int = 0
    status: Literal["pending", "running", "done", "error"] = "pending"


class AuditStep(BaseModel):
    """One agent-loop step as it is appended to output/audit_trail.json."""

    run_id: str
    seq: int
    ts: str
    t_ms: int
    agent: str
    agent_key: str
    kind: str = Field(
        description=(
            "user_prompt | model_request | model_response | mcp_tool_call | "
            "delegation_started | delegation_done | end | run_started | run_finished | error"
        )
    )
    step: int | None = None
    depth: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    """A job handed to the team — usually 'work the open tickets'."""

    message: str = Field(min_length=1)
    approved_by: str = ""
    allow_spending: bool = False


class RunResponse(BaseModel):
    run_id: str
    answer: str
    delegations: list[Delegation] = []
    usage: dict[str, Any] | None = None
    audit_steps: int = 0
    error: str | None = None

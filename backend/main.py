"""Campus Customs FastAPI backend — what the React dashboard talks to.

Start it from this folder:

    uvicorn main:app --reload --port 8000

Then the dashboard calls http://127.0.0.1:8000/... (plain HTTP — uvicorn is not
serving TLS here, so http:// rather than https://).
Interactive docs: http://127.0.0.1:8000/docs

Shop facts come from the Campus Customs MCP server via mcp_bridge, never from a
second data layer. The one exception is /reset, which copies the reference
database file over the working one — a filesystem operation, not a shop query.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mcp_bridge  # noqa: E402
from agents.team import run_team  # noqa: E402
from audit import list_runs, read_trail  # noqa: E402
from models import AGENT_ROSTER  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DB = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DB = PROJECT_ROOT / "data" / "campus_customs_new.db"

# Tickets in these states are finished as far as the dashboard is concerned.
CLOSED_STATUSES = {"resolved", "cancelled"}

# Background runs, so the dashboard can watch agents work instead of waiting on
# one long request. Process-local by design: this is a single-user class app.
RUNS: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_bridge.connect()
    try:
        yield
    finally:
        await mcp_bridge.disconnect()


app = FastAPI(
    title="Campus Customs",
    description="Backend for the agentic shop team. All shop data flows through the MCP server.",
    version="1.0.0",
    lifespan=lifespan,
)

# The Vite dev server runs on another port, so the browser needs CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ schemas


class RunTicketRequest(BaseModel):
    """Optional extra instruction when running one ticket."""

    note: str = ""


class ApprovalRequest(BaseModel):
    """A human clicking Approve. This is the only path that moves money."""

    kind: str = Field(description="'invoice' or 'rent'")
    ref_id: int = Field(description="invoices.id when kind='invoice', leases.id when kind='rent'")
    amount: float = Field(gt=0)
    approved_by: str = Field(min_length=1, description="Name of the human approving the spend")
    account: str = "checking"


# ------------------------------------------------------------------- routes


@app.get("/", summary="Route directory")
async def index() -> dict:
    return {
        "service": "Campus Customs backend",
        "database": WORKING_DB.name,
        "routes": {
            "GET /tickets": "the ticket queue with an open/resolved flag",
            "POST /tickets/{ticket_id}/run": "run the agent team on one ticket (blocks until done)",
            "POST /tickets/{ticket_id}/start": "start a run in the background, return its run_id now",
            "GET /runs/{run_id}": "status and result of a background run",
            "GET /agents": "the agent roster — names, remits and accent colours",
            "GET /events": "recent agent events — what each agent said and the tools it used",
            "POST /approve": "a human approves a payment; this route moves the cash",
            "GET /cash": "current checking balance",
            "POST /reset": "restore the working database from the reference copy",
            "GET /tools": "tool names the MCP server exposes",
        },
    }


@app.get("/tickets", summary="The 3 tickets and whether each is open or resolved")
async def get_tickets() -> dict:
    """Return every ticket with a simple is_open / is_resolved flag for the dashboard."""
    rows = await mcp_bridge.call("list_tickets", status="all")
    tickets = []
    for row in rows:
        status = row.get("status", "")
        tickets.append(
            {
                **row,
                "is_open": status not in CLOSED_STATUSES,
                "is_resolved": status in CLOSED_STATUSES,
                "needs_human": status == "needs_human",
            }
        )
    tickets.sort(key=lambda t: t["id"])
    return {
        "count": len(tickets),
        "open": sum(1 for t in tickets if t["is_open"]),
        "resolved": sum(1 for t in tickets if t["is_resolved"]),
        "tickets": tickets,
    }


@app.post("/tickets/{ticket_id}/run", summary="Run the agent team on one ticket")
async def run_ticket(ticket_id: int, body: RunTicketRequest | None = None) -> dict:
    """Hand one ticket to the Boss and let the team work it.

    Spending is always disabled on this route. The team investigates, decides and
    writes its recommendation; moving money is a separate human action on /approve.
    """
    rows = await mcp_bridge.call("list_tickets", status="all")
    ticket = next((r for r in rows if r.get("id") == ticket_id), None)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"No ticket with id {ticket_id}.")

    message = _ticket_run_message(ticket, body.note if body else "")
    result = await run_team(message, allow_spending=False)
    if result.get("error"):
        # The run still produced audit steps, so report it rather than hiding it.
        return {"ticket_id": ticket_id, "ok": False, **result}
    return {"ticket_id": ticket_id, "ok": True, **result}


def _ticket_run_message(ticket: dict, note: str = "") -> str:
    extra = f"\n\nExtra instruction from the shop owner: {note.strip()}" if note.strip() else ""
    return (
        f"Work ticket {ticket['id']} only: {ticket.get('subject')!r} "
        f"({ticket.get('type')}, raised by {ticket.get('requester')}). "
        "Verify every fact with the shop tools, delegate to the right specialists, "
        "and tell me what you decided and what still needs a human."
        f"{extra}"
    )


@app.post("/tickets/{ticket_id}/start", summary="Start a run in the background, return its id now")
async def start_ticket_run(ticket_id: int, body: RunTicketRequest | None = None) -> dict:
    """Kick off the agent team and return immediately with a run_id.

    The dashboard needs to show agents working *while* they work, so it starts
    the run here and then polls /events?run_id=... and /runs/{run_id}. Spending
    is disabled on this path too — only /approve moves money.
    """
    rows = await mcp_bridge.call("list_tickets", status="all")
    ticket = next((r for r in rows if r.get("id") == ticket_id), None)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"No ticket with id {ticket_id}.")

    active = next(
        (r for r in RUNS.values() if r["status"] == "running" and r["ticket_id"] == ticket_id),
        None,
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"Ticket {ticket_id} is already running as {active['run_id']}.",
        )

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    message = _ticket_run_message(ticket, body.note if body else "")
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running", "result": None}

    async def work() -> None:
        try:
            result = await run_team(message, allow_spending=False, run_id=run_id)
            RUNS[run_id]["result"] = result
            RUNS[run_id]["status"] = "error" if result.get("error") else "done"
        except Exception as exc:  # never leave the dashboard polling a dead run
            RUNS[run_id]["status"] = "error"
            RUNS[run_id]["result"] = {"run_id": run_id, "answer": "", "error": str(exc)}

    asyncio.create_task(work())
    return {"run_id": run_id, "ticket_id": ticket_id, "status": "running"}


@app.get("/runs/{run_id}", summary="Status and result of a background run")
async def get_run(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run {run_id}.")
    return run


def _flatten(trail: list[dict]) -> list[dict]:
    """Turn raw audit steps into the feed shape the dashboard renders.

    Each event is one of: something an agent said, an MCP tool it called, or a
    delegation between agents. Newest last, so the feed reads top to bottom.
    """
    events = []

    for step in trail:
        kind = step.get("kind")
        detail = step.get("detail", {})
        base = {
            "run_id": step.get("run_id"),
            "seq": step.get("seq"),
            "ts": step.get("ts"),
            "t_ms": step.get("t_ms"),
            "agent": step.get("agent"),
            "agent_key": step.get("agent_key"),
            "depth": step.get("depth", 0),
        }

        if kind == "model_response":
            said = (detail.get("text") or "").strip()
            calls = detail.get("tool_calls") or []
            if not said and not calls:
                continue
            events.append(
                {
                    **base,
                    "type": "said",
                    "text": said,
                    "tools_requested": [c.get("tool") for c in calls],
                    "usage": detail.get("usage"),
                }
            )
        elif kind == "mcp_tool_call":
            events.append(
                {
                    **base,
                    "type": "tool",
                    "tool": detail.get("tool"),
                    "args": detail.get("args"),
                    "is_write": detail.get("is_write", False),
                    "blocked": detail.get("blocked"),
                    "result": detail.get("result"),
                }
            )
        elif kind in ("delegation_started", "delegation_done"):
            events.append(
                {
                    **base,
                    "type": "delegation",
                    "phase": "started" if kind == "delegation_started" else "done",
                    "to_agent": detail.get("to_agent"),
                    "question": detail.get("question"),
                    "reply": detail.get("reply"),
                    "status": detail.get("status"),
                }
            )
        elif kind in ("run_started", "run_finished"):
            events.append({**base, "type": kind, "detail": detail})

    return events


def _runs_for_ticket(ticket_id: int) -> list[str]:
    """Run ids that worked this ticket, oldest first.

    The audit trail does not store a ticket id, but every run opens with a
    run_started step whose message names the ticket, so recover it from there.
    """
    found: list[str] = []
    for step in read_trail():
        if step.get("kind") != "run_started":
            continue
        message = str(step.get("detail", {}).get("message", ""))
        match = re.search(r"[Ww]ork ticket (\d+)", message)
        if match and int(match.group(1)) == ticket_id:
            found.append(step["run_id"])
    return found


@app.get("/events", summary="Recent agent events — what agents said and which tools they used")
async def get_events(limit: int = 60, run_id: str | None = None) -> dict:
    events = _flatten(read_trail(run_id))
    total = len(events)
    return {
        "total_events": total,
        "returned": min(limit, total),
        "runs": list_runs()[:10],
        "events": events[-limit:],
    }


@app.get("/tickets/{ticket_id}/history", summary="The most recent run worked on this ticket")
async def ticket_history(ticket_id: int, limit: int = 400) -> dict:
    """Replay the last run for a ticket, so selecting it shows real history.

    Without this the dashboard goes blank on reload and a finished ticket looks
    like nothing ever happened to it.
    """
    runs = _runs_for_ticket(ticket_id)
    if not runs:
        return {"ticket_id": ticket_id, "run_id": None, "events": [], "runs": []}
    latest = runs[-1]
    return {
        "ticket_id": ticket_id,
        "run_id": latest,
        "runs": runs,
        "events": _flatten(read_trail(latest))[-limit:],
    }


@app.post("/approve", summary="Human approves a payment — this route moves the cash")
async def approve_payment(req: ApprovalRequest) -> dict:
    """Record a payment the agents only recommended.

    The agent team can never reach this: /tickets/{id}/run always disables
    spending. A payment happens because a person clicked Approve, and their name
    is written onto the ledger row.

    The MCP tool still enforces its own rules — the amount must match the
    obligation on file, the account must cover it, and the same obligation
    cannot be paid twice.
    """
    result = await mcp_bridge.call(
        "record_payment",
        kind=req.kind,
        ref_id=req.ref_id,
        amount=req.amount,
        account=req.account,
        approved_by=req.approved_by,
    )
    if not result.get("ok"):
        # A refusal is a 400, not a 500 — the request was understood and declined.
        raise HTTPException(status_code=400, detail=result.get("error", "Payment refused."))
    return result


@app.get("/cash", summary="Current checking balance")
async def get_cash() -> dict:
    """Return the checking balance plus what is still owed against it."""
    position = await mcp_bridge.call("get_cash_position")
    checking = next(
        (a for a in position.get("accounts", []) if a.get("name") == "checking"),
        None,
    )
    return {
        "checking_balance": checking["balance"] if checking else None,
        "as_of": checking["date"] if checking else None,
        "shop_date": position.get("shop_date"),
        "committed_outflows": position.get("committed_outflows"),
        "cash_after_commitments": position.get("cash_after_commitments"),
        "open_invoices": position.get("open_invoices", []),
        "leases": position.get("leases", []),
        "accounts": position.get("accounts", []),
    }


@app.post("/reset", summary="Reset the working database to the original values")
async def reset_database() -> dict:
    """Copy the pristine reference database over the working one.

    This is a file copy rather than an MCP call on purpose: it replaces the
    database rather than querying it, so there is nothing for a shop tool to do.
    The reference copy is only ever read, never written.

    The audit trail is deliberately left alone — it is the record of what the
    agents did, and a data reset should not erase history.
    """
    if not REFERENCE_DB.exists():
        raise HTTPException(status_code=500, detail=f"Reference database missing: {REFERENCE_DB}")

    # Drop the MCP connection first so no open handle survives the swap.
    await mcp_bridge.disconnect()
    try:
        shutil.copyfile(REFERENCE_DB, WORKING_DB)
    except OSError as exc:
        await mcp_bridge.connect()
        raise HTTPException(status_code=500, detail=f"Reset failed: {exc}") from exc
    await mcp_bridge.connect()

    tickets = await mcp_bridge.call("list_tickets", status="all")
    cash = await mcp_bridge.call("get_cash_position")
    return {
        "ok": True,
        "restored_from": REFERENCE_DB.name,
        "restored_to": WORKING_DB.name,
        "tickets": {t["id"]: t["status"] for t in tickets},
        "checking_balance": next(
            (a["balance"] for a in cash.get("accounts", []) if a["name"] == "checking"), None
        ),
        "audit_trail": "left intact — reset restores shop data, not the agent history",
    }


@app.get("/agents", summary="The agent roster")
async def get_agents() -> dict:
    """Who is on the team, what each one owns, and the accent colour the UI uses."""
    return {"agents": AGENT_ROSTER}


@app.get("/tools", summary="Tool names the MCP server exposes")
async def get_tools() -> dict:
    return {"server": "campus-customs", "tools": await mcp_bridge.list_tool_names()}

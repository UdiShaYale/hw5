"""The Campus Customs agent team — Boss, Inventory, Accounting, Facilities, CS.

Full connectivity: every agent carries the same `ask_teammate` tool and can
reach every other agent, including back to the Boss. Inventory can ask
Accounting whether a reprint is affordable; Accounting can ask Facilities what
rent is really due; Customer Service can ask either before promising anything.

What stops that from spiralling:
  * MAX_DEPTH      — how deep a delegation chain may go
  * MAX_DELEGATIONS— how many delegations a whole run may make
  * a cycle guard  — an agent already active in this chain cannot be re-entered
  * UsageLimits    — a per-agent ceiling on model requests

All shop facts come from the MCP toolset in shop_mcp.py. No agent touches SQLite.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits

from agents.config import (
    MAX_DELEGATIONS,
    MAX_DEPTH,
    MAX_REQUESTS_PER_AGENT,
    MODEL_NAME,
    build_model,
)
from agents.loop import clip, run_traced
from agents.shop_mcp import build_shop_toolset
from audit import append_step, new_step
from models import AGENT_NAMES, AGENTS_BY_KEY, AGENT_ROSTER, SPECIALIST_KEYS

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(key: str) -> str:
    return (PROMPT_DIR / f"{key}.md").read_text(encoding="utf-8")


# --------------------------------------------------------------- run state


@dataclass
class RunState:
    """Counters shared by every agent in one run (the whole delegation tree)."""

    run_id: str
    started: float = field(default_factory=time.perf_counter)
    seq: int = 0
    tool_calls: int = 0
    delegations: list[dict] = field(default_factory=list)
    usages: list[dict] = field(default_factory=list)
    audit_steps: int = 0
    allow_spending: bool = False
    approved_by: str = ""


@dataclass
class TeamDeps:
    """Per-agent dependency bundle. Nested agents share the same RunState."""

    state: RunState
    agent_key: str
    depth: int = 0
    # Agents currently on the call stack — used to refuse cycles.
    chain: tuple[str, ...] = ()

    @property
    def agent_name(self) -> str:
        return AGENT_NAMES[self.agent_key]

    @property
    def allow_spending(self) -> bool:
        return self.state.allow_spending

    def emit(self, kind: str, **detail: Any) -> None:
        """Write one agent-loop step to output/audit_trail.json."""
        s = self.state
        s.seq += 1
        step_detail = dict(detail)
        step_number = step_detail.pop("step", None)
        record = new_step(
            run_id=s.run_id,
            seq=s.seq,
            started=s.started,
            agent=self.agent_name,
            agent_key=self.agent_key,
            kind=kind,
            step=step_number,
            depth=self.depth,
            **step_detail,
        )
        s.audit_steps = append_step(record)

    def child(self, agent_key: str) -> "TeamDeps":
        return TeamDeps(
            state=self.state,
            agent_key=agent_key,
            depth=self.depth + 1,
            chain=self.chain + (self.agent_key,),
        )


# ------------------------------------------------------------ agent registry

_AGENTS: dict[str, Agent] = {}

_TEAMMATE_DIRECTORY = "\n".join(
    f"- `{a['key']}` — {a['name']}: {a['remit']}" for a in AGENT_ROSTER
)


def _build_agent(key: str) -> Agent:
    """Build one agent: its prompt, the shared MCP toolset, and ask_teammate."""
    spec = AGENTS_BY_KEY[key]
    base_prompt = load_prompt(key)

    agent = Agent(
        deps_type=TeamDeps,
        output_type=str,
        name=spec["name"],
        toolsets=[build_shop_toolset()],
        retries=2,
    )

    @agent.instructions
    def _instructions(ctx: RunContext[TeamDeps]) -> str:
        d = ctx.deps
        spending = (
            f"Spending IS approved for this run by {d.state.approved_by or 'an unnamed approver'}. "
            "You may call record_payment, but only for an amount that matches the obligation on file."
            if d.allow_spending
            else "Spending is NOT approved for this run. You must not call record_payment. "
            "Recommend the payment in writing and set the ticket to needs_human instead."
        )
        return (
            f"{base_prompt}\n\n"
            "## Your team\n\n"
            f"{_TEAMMATE_DIRECTORY}\n\n"
            "You can reach any of them with `ask_teammate`. Delegate when the question "
            "belongs to someone else's remit rather than guessing at it yourself.\n\n"
            "## This run\n\n"
            f"- You are `{d.agent_key}` ({d.agent_name}), at delegation depth {d.depth} of {MAX_DEPTH}.\n"
            f"- {spending}\n"
            f"- Shop facts come only from the campus-customs MCP tools. If a tool did not "
            f"return a fact, you do not know it — say so rather than filling the gap.\n"
        )

    @agent.tool
    async def ask_teammate(ctx: RunContext[TeamDeps], agent_key: str, question: str) -> dict:
        """Ask another agent on the team to handle something in their remit.

        Args:
            agent_key: one of boss, inventory, accounting, facilities, customer_service.
            question: a specific, self-contained question. The teammate does not see
                your conversation, so include the ticket number, SKU, size, amounts
                and anything else they need to act.
        """
        d = ctx.deps
        state = d.state

        if agent_key not in AGENTS_BY_KEY:
            return {
                "status": "error",
                "reply": f"Unknown teammate {agent_key!r}. Choose from {list(AGENTS_BY_KEY)}.",
            }
        if agent_key == d.agent_key:
            return {"status": "error", "reply": "You cannot delegate to yourself."}
        if agent_key in d.chain:
            return {
                "status": "error",
                "reply": (
                    f"{AGENT_NAMES[agent_key]} is already waiting on you further up this chain. "
                    "Answer with what you have instead of looping back."
                ),
            }
        if d.depth >= MAX_DEPTH:
            return {
                "status": "error",
                "reply": f"Delegation depth limit ({MAX_DEPTH}) reached. Answer from what you know.",
            }
        if len(state.delegations) >= MAX_DELEGATIONS:
            return {
                "status": "error",
                "reply": f"Delegation budget ({MAX_DELEGATIONS}) spent for this run. Answer now.",
            }

        index = len(state.delegations)
        record = {
            "from_agent": d.agent_name,
            "to_agent": AGENT_NAMES[agent_key],
            "agent_key": agent_key,
            "question": question,
            "reply": "",
            "depth": d.depth + 1,
            "status": "running",
        }
        state.delegations.append(record)
        d.emit(
            "delegation_started",
            index=index,
            to_agent=AGENT_NAMES[agent_key],
            to_key=agent_key,
            question=clip(question, 600),
        )

        child_deps = d.child(agent_key)
        try:
            reply, usage = await run_traced(
                get_agent(agent_key),
                question,
                emit=child_deps.emit,
                deps=child_deps,
                model=build_model(),
                usage_limits=UsageLimits(request_limit=MAX_REQUESTS_PER_AGENT),
            )
            reply = (reply or "").strip()
            state.usages.append({"agent": agent_key, **usage})
            record.update(reply=reply, status="done")
            status = "done"
        except Exception as exc:
            reply = f"{AGENT_NAMES[agent_key]} could not complete that: {clip(exc, 300)}"
            record.update(reply=reply, status="error")
            status = "error"

        d.emit(
            "delegation_done",
            index=index,
            to_agent=AGENT_NAMES[agent_key],
            to_key=agent_key,
            status=status,
            reply=clip(reply, 800),
        )
        return {"status": status, "agent": AGENT_NAMES[agent_key], "reply": reply}

    return agent


def get_agent(key: str) -> Agent:
    """Agents are built lazily so the five can reference each other freely."""
    if key not in _AGENTS:
        _AGENTS[key] = _build_agent(key)
    return _AGENTS[key]


# ----------------------------------------------------------------- run entry


def _total_usage(state: RunState, boss_usage: dict | None) -> dict:
    parts = ([boss_usage] if boss_usage else []) + state.usages
    keys = ("requests", "input_tokens", "output_tokens", "tool_calls")
    return {
        "model": MODEL_NAME,
        "boss": boss_usage,
        "specialists": {k: sum(p.get(k, 0) for p in state.usages) for k in keys},
        "total": {k: sum(p.get(k, 0) for p in parts) for k in keys},
        "mcp_tool_calls": state.tool_calls,
        "delegations": len(state.delegations),
    }


async def run_team(
    message: str,
    *,
    approved_by: str = "",
    allow_spending: bool = False,
    run_id: str | None = None,
) -> dict:
    """Hand a job to the Boss and let the team work it. Appends to the audit trail."""
    state = RunState(
        run_id=run_id or f"run-{uuid.uuid4().hex[:8]}",
        allow_spending=allow_spending,
        approved_by=approved_by,
    )
    deps = TeamDeps(state=state, agent_key="boss", depth=0)
    boss_usage: dict | None = None

    deps.emit(
        "run_started",
        message=clip(message, 600),
        model=MODEL_NAME,
        allow_spending=allow_spending,
        approved_by=approved_by,
        limits={
            "max_delegations": MAX_DELEGATIONS,
            "max_depth": MAX_DEPTH,
            "max_requests_per_agent": MAX_REQUESTS_PER_AGENT,
        },
    )

    try:
        answer, boss_usage = await run_traced(
            get_agent("boss"),
            message,
            emit=deps.emit,
            deps=deps,
            model=build_model(),
            usage_limits=UsageLimits(request_limit=MAX_REQUESTS_PER_AGENT),
        )
        answer = (answer or "").strip()
        error = None
    except Exception as exc:
        answer = f"The run stopped early: {clip(exc, 400)}"
        error = clip(exc, 1000)

    usage = _total_usage(state, boss_usage)
    deps.emit("run_finished", answer=clip(answer, 1200), usage=usage, error=error)

    return {
        "run_id": state.run_id,
        "answer": answer,
        "delegations": state.delegations,
        "usage": usage,
        "audit_steps": state.audit_steps,
        "error": error,
    }


__all__ = ["run_team", "get_agent", "TeamDeps", "RunState", "SPECIALIST_KEYS"]

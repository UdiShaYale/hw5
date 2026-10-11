"""Append-only audit trail at output/audit_trail.json.

Every agent-loop step from every agent lands here, including every MCP tool call.
The file accumulates across runs and is never wiped: each append reads the
existing array, adds the new step, and rewrites atomically via a temp file +
os.replace, so a crash mid-write cannot truncate the history.

Grouping is by `run_id`, so the dashboard can show one run at a time while the
file keeps the full history behind it.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
AUDIT_PATH = OUTPUT_DIR / "audit_trail.json"

_lock = threading.Lock()


def _read_existing() -> list[dict]:
    """Load the trail so far. A corrupt or missing file never loses old steps."""
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Keep the damaged file rather than silently dropping it on the floor.
        backup = AUDIT_PATH.with_suffix(f".corrupt-{int(time.time())}.json")
        AUDIT_PATH.replace(backup)
        return []
    return data if isinstance(data, list) else []


def _write_trail(trail: list[dict]) -> None:
    """Write the trail out, preferring an atomic replace.

    This project lives in a OneDrive-synced folder, where the sync client can
    hold a transient lock on the destination and make os.replace fail with
    WinError 5. Retry briefly, then fall back to writing in place rather than
    losing the step.
    """
    payload = json.dumps(trail, indent=2, default=str) + "\n"
    tmp = AUDIT_PATH.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")

    for attempt in range(5):
        try:
            os.replace(tmp, AUDIT_PATH)
            return
        except PermissionError:
            time.sleep(0.1 * (attempt + 1))

    AUDIT_PATH.write_text(payload, encoding="utf-8")
    tmp.unlink(missing_ok=True)


def append_step(step: dict[str, Any]) -> int:
    """Append one agent-loop step. Returns the trail's new total length."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        trail = _read_existing()
        trail.append(step)
        _write_trail(trail)
        return len(trail)


def new_step(
    *,
    run_id: str,
    seq: int,
    started: float,
    agent: str,
    agent_key: str,
    kind: str,
    step: int | None = None,
    depth: int = 0,
    **detail: Any,
) -> dict:
    return {
        "run_id": run_id,
        "seq": seq,
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "t_ms": round((time.perf_counter() - started) * 1000),
        "agent": agent,
        "agent_key": agent_key,
        "kind": kind,
        "step": step,
        "depth": depth,
        "detail": detail,
    }


def read_trail(run_id: str | None = None) -> list[dict]:
    """Read the trail back, optionally filtered to one run."""
    with _lock:
        trail = _read_existing()
    if run_id:
        return [s for s in trail if s.get("run_id") == run_id]
    return trail


def list_runs() -> list[dict]:
    """Summarise each run in the trail, newest first."""
    runs: dict[str, dict] = {}
    for step in read_trail():
        rid = step.get("run_id", "unknown")
        entry = runs.setdefault(rid, {"run_id": rid, "steps": 0, "started_at": step.get("ts")})
        entry["steps"] += 1
        entry["ended_at"] = step.get("ts")
    return sorted(runs.values(), key=lambda r: r.get("started_at") or "", reverse=True)

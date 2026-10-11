"""Drive all three tickets to a final status, recording what happened.

Pass 1 runs each ticket. Where the team recommends a payment, a human approval
is applied through /approve (the only path that moves cash). Pass 2 re-runs the
ticket, telling the Boss what was approved so it can close the ticket out.

Writes output/board_runs.json — the raw record the HTML pages are built from.

    python resolve_board.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "output" / "board_runs.json"
APPROVER = "Uditaa Shandilya"

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def api(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"_error": json.loads(exc.read() or b"{}").get("detail", str(exc)), "_status": exc.code}


def cash() -> float:
    return api("/cash")["checking_balance"]


def ticket(tid: int) -> dict:
    return next(t for t in api("/tickets")["tickets"] if t["id"] == tid)


def run_ticket(tid: int, note: str = "") -> dict:
    """Start a background run and wait for it, returning run id + events."""
    started = api(f"/tickets/{tid}/start", "POST", {"note": note})
    if "_error" in started:
        raise RuntimeError(started["_error"])
    rid = started["run_id"]
    print(f"    run {rid} …", end="", flush=True)

    t0 = time.time()
    while True:
        time.sleep(5)
        status = api(f"/runs/{rid}")
        if status["status"] != "running":
            break
        if time.time() - t0 > 800:
            raise RuntimeError(f"run {rid} timed out")
    secs = round(time.time() - t0)
    print(f" {status['status']} in {secs}s")

    events = api(f"/events?run_id={rid}&limit=500")["events"]
    return {
        "run_id": rid,
        "status": status["status"],
        "seconds": secs,
        "result": status.get("result") or {},
        "events": events,
    }


def summarise(events: list[dict]) -> dict:
    """Per-agent: tools used, delegations made, closing statement."""
    agents: dict[str, dict] = {}
    for e in events:
        key = e.get("agent_key")
        if not key:
            continue
        a = agents.setdefault(
            key,
            {"agent": e["agent"], "tools": [], "writes": [], "blocked": [],
             "delegated_to": [], "said": [], "max_depth": 0},
        )
        a["max_depth"] = max(a["max_depth"], e.get("depth", 0))
        if e["type"] == "tool":
            if e.get("blocked"):
                a["blocked"].append(e["tool"])
            else:
                a["tools"].append(e["tool"])
                if e.get("is_write"):
                    a["writes"].append({"tool": e["tool"], "args": e.get("args")})
        elif e["type"] == "delegation" and e.get("phase") == "started":
            a["delegated_to"].append(e.get("to_agent"))
        elif e["type"] == "said" and (e.get("text") or "").strip():
            a["said"].append(e["text"].strip())

    for a in agents.values():
        a["tools_used"] = sorted(set(a["tools"]))
        a["tool_calls"] = len(a["tools"])
        a["closing"] = a["said"][-1] if a["said"] else ""
        del a["tools"], a["said"]

    delegations = [
        {"from": e["agent"], "to": e.get("to_agent"), "depth": e.get("depth", 0),
         "question": (e.get("question") or "")[:260]}
        for e in events
        if e["type"] == "delegation" and e.get("phase") == "started"
    ]
    tool_calls = [
        {"agent": e["agent"], "tool": e["tool"], "args": e.get("args"),
         "is_write": bool(e.get("is_write")), "blocked": bool(e.get("blocked"))}
        for e in events if e["type"] == "tool"
    ]
    return {"agents": agents, "delegations": delegations, "tool_calls": tool_calls}


# Payment each ticket is expected to unblock, if the shop can afford it.
PAYMENTS = {
    101: {"kind": "invoice", "ref_id": 501, "amount": 840.0,
          "why": "Invoice 501 is the rush reprint of CC-TEE-WHITE size S — the stockout behind this ticket."},
    102: {"kind": "rent", "ref_id": 1, "amount": 2400.0,
          "why": "Lease 1 rent for the Chapel Street shop, due 2026-09-02."},
    103: None,  # nothing on file to pay; a reprint quote does not exist in the database
}

CLOSE_NOTE = (
    "Update: a human has reviewed your recommendation. {paid}"
    "Nothing further is awaiting an approval on this ticket. Re-check the shop tools for the "
    "current state, tell the customer what is true now, and close the ticket out with "
    "update_ticket_status — use 'resolved' if nothing is outstanding that the shop still owes "
    "this requester, or 'cancelled' if the request cannot be fulfilled at all. Do not leave it "
    "as needs_human unless a further human approval is genuinely still required."
)


def main() -> int:
    board: dict = {"approver": APPROVER, "tickets": {}}

    start_balance = cash()
    board["starting_balance"] = start_balance
    print(f"\nStarting checking balance after reset: ${start_balance:,.2f}\n")

    for tid in (101, 102, 103):
        print(f"=== ticket {tid} ===")
        entry: dict = {"ticket_id": tid, "runs": [], "approvals": [], "cash": {}}
        before = cash()
        entry["cash"]["before"] = before

        # --- pass 1: investigate -------------------------------------------
        print("  pass 1 — investigate")
        r1 = run_ticket(tid)
        entry["runs"].append({**r1, "pass": 1, "summary": summarise(r1["events"])})
        status_after_1 = ticket(tid)["status"]
        entry["status_after_pass_1"] = status_after_1
        print(f"    status: {status_after_1}")

        # --- human approval -------------------------------------------------
        pay = PAYMENTS[tid]
        paid_note = ""
        if pay:
            avail = cash()
            if pay["amount"] <= avail:
                print(f"  human approves {pay['kind']} {pay['ref_id']} ${pay['amount']:,.2f}")
                res = api("/approve", "POST", {
                    "kind": pay["kind"], "ref_id": pay["ref_id"],
                    "amount": pay["amount"], "approved_by": APPROVER,
                })
                if "_error" in res:
                    print(f"    REFUSED: {res['_error']}")
                    entry["approvals"].append({"requested": pay, "refused": res["_error"]})
                else:
                    entry["approvals"].append({
                        "kind": res["kind"], "ref_id": res["ref_id"], "amount": res["amount"],
                        "approved_by": res["approved_by"], "paid_at": res["paid_at"],
                        "payment_id": res["payment_id"], "new_balance": res["new_balance"],
                        "why": pay["why"],
                    })
                    paid_note = (
                        f"They approved and recorded a payment of ${res['amount']:,.2f} for "
                        f"{res['kind']} {res['ref_id']} (payment id {res['payment_id']}, "
                        f"approved by {res['approved_by']}). Checking is now "
                        f"${res['new_balance']:,.2f}. "
                    )
                    print(f"    paid — balance now ${res['new_balance']:,.2f}")
            else:
                print(f"  cannot approve ${pay['amount']:,.2f}: only ${avail:,.2f} available")
                entry["approvals"].append({
                    "requested": pay, "refused": f"insufficient funds: ${avail:,.2f} available"
                })
                paid_note = (
                    f"They reviewed it and did NOT approve a payment — checking holds only "
                    f"${avail:,.2f}. No money is available for this ticket. "
                )
        else:
            paid_note = (
                "They reviewed it and found nothing on file to pay: the database holds no quote "
                "or invoice for this request, so no payment could be approved. "
            )

        # --- pass 2: close out ----------------------------------------------
        print("  pass 2 — close out")
        r2 = run_ticket(tid, CLOSE_NOTE.format(paid=paid_note))
        entry["runs"].append({**r2, "pass": 2, "summary": summarise(r2["events"])})

        final = ticket(tid)
        after = cash()
        entry["final_status"] = final["status"]
        entry["final_notes"] = final["notes"]
        entry["cash"]["after"] = after
        entry["cash"]["change"] = round(after - before, 2)
        print(f"    FINAL: {final['status']} | cash {before:,.2f} -> {after:,.2f} "
              f"({after - before:+,.2f})\n")

        board["tickets"][str(tid)] = entry

    board["ending_balance"] = cash()
    board["total_change"] = round(board["ending_balance"] - start_balance, 2)
    board["payments_ledger"] = api("/events?limit=1")  # placeholder, replaced below
    del board["payments_ledger"]

    OUT.write_text(json.dumps(board, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Starting balance : ${start_balance:,.2f}")
    print(f"Ending balance   : ${board['ending_balance']:,.2f}")
    print(f"Net change       : ${board['total_change']:+,.2f}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

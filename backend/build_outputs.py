"""Build the final artefacts from output/board_runs.json and the live database.

    python build_outputs.py

Writes:
  output/resolved_tickets.json  — per ticket: status, outcome, agent contributions, approvals
  output/desk_tickets.html      — fills the Actual sections and the Cash tab
  output/resolved_board.html    — the dashboard screenshots per ticket
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
DB = ROOT / "data" / "campus_customs_new.db"

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

board = json.loads((OUT / "board_runs.json").read_text(encoding="utf-8"))


def db_rows(sql: str) -> list[dict]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def merged(tid: str) -> dict:
    """Union every pass for one ticket into a single picture."""
    entry = board["tickets"][tid]
    agents: dict[str, dict] = {}
    delegations: list[dict] = []
    tool_calls: list[dict] = []

    for run in entry["runs"]:
        s = run["summary"]
        for key, v in s["agents"].items():
            a = agents.setdefault(
                key,
                {"agent": v["agent"], "tools": set(), "writes": [], "blocked": set(),
                 "delegated_to": [], "closing": "", "tool_calls": 0, "max_depth": 0},
            )
            a["tools"] |= set(v["tools_used"])
            a["blocked"] |= set(v["blocked"])
            a["writes"] += v["writes"]
            a["delegated_to"] += [d for d in v["delegated_to"] if d]
            a["tool_calls"] += v["tool_calls"]
            a["max_depth"] = max(a["max_depth"], v["max_depth"])
            if v["closing"]:
                a["closing"] = v["closing"]
        delegations += [{**d, "pass": run["pass"]} for d in s["delegations"]]
        tool_calls += [{**t, "pass": run["pass"]} for t in s["tool_calls"]]

    for a in agents.values():
        a["tools"] = sorted(a["tools"])
        a["blocked"] = sorted(a["blocked"])
        a["delegated_to"] = sorted(set(a["delegated_to"]))

    return {"entry": entry, "agents": agents, "delegations": delegations, "tool_calls": tool_calls}


DATA = {tid: merged(tid) for tid in ("101", "102", "103")}

# --------------------------------------------------------------------------
# 1. resolved_tickets.json
# --------------------------------------------------------------------------

OUTCOMES = {
    "101": (
        "Size S was out of stock (qty 0) and could not be filled. The team traced the "
        "ticket's invoice_id to invoice 501 — the $840 rush reprint of this exact SKU and "
        "size, 3 days overdue — and recommended paying it. A human approved that payment, "
        "which closed the invoice. The ticket stayed in_progress rather than resolved: the "
        "reprint is paid for but has not arrived, and the agents refused to call the "
        "customer's request finished while the goods are still outstanding."
    ),
    "102": (
        "The rent notice was verified against lease 1: Elm City Properties is the landlord "
        "of record, rent is $2,400, and next_due 2026-09-02 is exactly 2 days from the shop "
        "date of 2026-08-31, so the 'due in 2 days' claim held. The team flagged that the "
        "notice itself named no amount — the $2,400 came only from the lease row. A human "
        "approved the rent payment and the ticket was resolved."
    ),
    "103": (
        "Only 8 of the 20 hoodies requested were in stock in size M — a 12-unit shortfall "
        "that the other sizes (S 4, L 14, XL 6) cannot cover. Margin headroom is $36/unit "
        "($58 list − $22 cost), but no tool returns a reprint quote, so the team would not "
        "certify any discount as profitable end-to-end. With $160 left after rent and "
        "invoice 501, the reprint could not be funded. Resolved by telling the club what the "
        "shop can actually supply, with no discount approved and no money spent."
    ),
}

resolved = {
    "generated_from": "output/board_runs.json",
    "shop_date": "2026-08-31",
    "database": "data/campus_customs_new.db",
    "approver": board["approver"],
    "starting_checking_balance": board["starting_balance"],
    "ending_checking_balance": board["ending_balance"],
    "tickets": [],
}

for tid in ("101", "102", "103"):
    d = DATA[tid]
    e = d["entry"]
    resolved["tickets"].append({
        "id": int(tid),
        "final_status": e["final_status"],
        "outcome": OUTCOMES[tid],
        "runs": [{"pass": r["pass"], "run_id": r["run_id"], "status": r["status"],
                  "seconds": r["seconds"], "events": len(r["events"])} for r in e["runs"]],
        "agents": {
            key: {
                "name": a["agent"],
                "tool_calls": a["tool_calls"],
                "tools_used": a["tools"],
                "delegated_to": a["delegated_to"],
                "writes": a["writes"],
                "max_delegation_depth": a["max_depth"],
                "contribution": a["closing"],
            }
            for key, a in d["agents"].items()
        },
        "delegations": [
            {"from": x["from"], "to": x["to"], "depth": x["depth"], "pass": x["pass"]}
            for x in d["delegations"]
        ],
        "human_approvals": e["approvals"],
        "cash": e["cash"],
        "final_ticket_notes": e["final_notes"],
    })

resolved["payments_ledger"] = db_rows("SELECT * FROM payments ORDER BY id")
resolved["verification"] = {
    "cash_accounts_balance": db_rows("SELECT balance FROM cash_accounts")[0]["balance"],
    "ticket_statuses": {str(r["id"]): r["status"] for r in db_rows("SELECT id, status FROM tickets")},
    "invoice_statuses": {str(r["id"]): r["status"] for r in db_rows("SELECT id, status FROM invoices")},
}

(OUT / "resolved_tickets.json").write_text(
    json.dumps(resolved, indent=2, default=str) + "\n", encoding="utf-8"
)
print("wrote resolved_tickets.json")

# --------------------------------------------------------------------------
# 2. desk_tickets.html — Actual sections + Cash tab
# --------------------------------------------------------------------------

AGENT_ORDER = ["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_LABEL = {
    "boss": "Shop Boss", "inventory": "Inventory", "accounting": "Accounting",
    "facilities": "Facilities", "customer_service": "Customer Service",
}

# How the prediction held up, written against the run data below it.
VERDICTS = {
    "101": {
        "first_call": ("hit", "Inventory", "Predicted Inventory. The Boss delegated to Inventory first in pass 1, before touching price or payment."),
        "notes": [
            ("hit", "Inventory → Accounting fired.", "The cross-link predicted as the proof of real connectivity happened in pass 2 — Inventory reached Accounting about invoice 501 without the Boss routing it."),
            ("hit", "Customer Service checked before promising.", "Marked only 'possible' in the prediction, but CS delegated to both Inventory and Accounting in every pass before drafting a reply."),
            ("hit", "Facilities stayed out.", "Correctly never involved — this ticket has no lease dimension."),
            ("hit", "No date was promised.", "The team repeatedly refused to give a restock date, because lead_days is a vendor lead time and no order confirmation exists in the database."),
            ("miss", "It did not reach 'resolved'.", "The prediction said needs_human, which pass 1 produced. After the payment was approved it went to in_progress, not resolved — the agents would not close a ticket whose goods have not arrived."),
        ],
    },
    "102": {
        "first_call": ("hit", "Facilities", "Predicted Facilities, on the grounds that an inbound claim must be verified before it is priced. That is exactly what happened."),
        "notes": [
            ("hit", "Facilities → Accounting fired.", "Predicted precisely: Facilities verified the lease, then asked Accounting whether the cash was there rather than deciding affordability itself."),
            ("hit", "The missing amount was caught.", "The prediction flagged that the notice names no figure. The team reported that the $2,400 came only from the lease row and that the notice itself stated no amount."),
            ("hit", "The date claim was checked, not accepted.", "next_due 2026-09-02 was compared against the shop date rather than taking 'due in 2 days' at face value."),
            ("hit", "Reached resolved after approval.", "As predicted, needs_human first, then closed once a human approved the rent."),
        ],
    },
    "103": {
        "first_call": ("miss", "Inventory", "Predicted Accounting — reasoning that the Boss would be pulled by the ticket's price_override label. It was not. The Boss delegated to Inventory first, which is the call the prediction argued was correct but did not expect. The Boss read what the ticket needed rather than what it was labelled."),
        "notes": [
            ("hit", "Accounting → Inventory fired.", "Predicted: Accounting could not finish a margin answer without knowing how many could be supplied, and it made that hop itself."),
            ("hit", "The 12-unit shortfall was caught.", "8 on hand against 20 requested. No agent summed the SKU across sizes."),
            ("hit", "The unknown reprint cost was caught.", "The prediction's sharpest call. The team declined to treat the $22 unit_cost as a reprint quote and would not certify the deal profitable without one."),
            ("hit", "No discount was approved.", "Margin headroom of $36/unit was quoted as a bound, not as an offer."),
        ],
    },
}


def chip(kind: str) -> str:
    return f'<span class="verdict-chip {kind}">{"as predicted" if kind == "hit" else "differed"}</span>'


def actual_section(tid: str) -> str:
    d = DATA[tid]
    e = d["entry"]
    v = VERDICTS[tid]
    first_kind, first_who, first_text = v["first_call"]

    passes = "".join(
        f"<tr><td>Pass {r['pass']}</td><td class='mono'>{r['run_id']}</td>"
        f"<td class='tnum'>{len(r['events'])}</td><td class='tnum'>{r['seconds']}s</td>"
        f"<td>{'ok' if r['status'] == 'done' else escape(str(r['status']))}</td></tr>"
        for r in e["runs"]
    )

    deleg_rows = "".join(
        f"<tr><td>{r['pass']}</td><td>{escape(r['from'])}</td>"
        f"<td class='arrow'>&rarr;</td><td>{escape(str(r['to']))}</td>"
        f"<td class='tnum'>d{r['depth']}</td></tr>"
        for r in d["delegations"]
    )

    # tool -> which agents called it, how many times
    tool_map: dict[str, dict[str, int]] = {}
    for t in d["tool_calls"]:
        if t["blocked"]:
            continue
        tool_map.setdefault(t["tool"], {}).setdefault(t["agent"], 0)
        tool_map[t["tool"]][t["agent"]] += 1
    tool_rows = "".join(
        f"<tr><td><code>{escape(tool)}</code></td>"
        f"<td class='tnum'>{sum(by.values())}</td>"
        f"<td>{escape(', '.join(f'{a} ×{n}' for a, n in sorted(by.items())))}</td></tr>"
        for tool, by in sorted(tool_map.items())
    )

    agent_cards = "".join(
        f"""<div class="agent-row">
          <div class="agent-row-head"><strong>{escape(d['agents'][k]['agent'])}</strong>
            <span class="tnum">{d['agents'][k]['tool_calls']} tool calls</span>
            {f"<span class='tnum'>{len(d['agents'][k]['writes'])} writes</span>" if d['agents'][k]['writes'] else ''}
            {f"<span>asked {escape(', '.join(d['agents'][k]['delegated_to']))}</span>" if d['agents'][k]['delegated_to'] else ''}
          </div>
          <p>{escape((d['agents'][k]['closing'] or '')[:420])}{'…' if len(d['agents'][k]['closing'] or '') > 420 else ''}</p>
        </div>"""
        for k in AGENT_ORDER if k in d["agents"]
    )
    absent = [AGENT_LABEL[k] for k in AGENT_ORDER if k not in d["agents"]]

    approvals = e["approvals"]
    if approvals and "payment_id" in approvals[0]:
        a = approvals[0]
        appr = (
            f"<p><strong>${a['amount']:,.2f}</strong> for {escape(a['kind'])} {a['ref_id']}, "
            f"approved by <strong>{escape(a['approved_by'])}</strong> on {a['paid_at']} "
            f"(payment #{a['payment_id']}). Checking went to ${a['new_balance']:,.2f}.</p>"
            f"<p class='small'>{escape(a['why'])}</p>"
        )
    else:
        appr = "<p>None. No payment was approved for this ticket.</p>"

    notes = "".join(
        f"<li>{chip(kind)} <strong>{escape(title)}</strong> {escape(body)}</li>"
        for kind, title, body in v["notes"]
    )

    return f"""<section class="band actual">
    <h2 class="band-title">Actual <span class="note">from the run on 2026-08-31</span></h2>

    <div class="card">
      <h3><span class="num">1</span> Who the boss called first</h3>
      <p><strong>{escape(first_who)}.</strong> {chip(first_kind)}</p>
      <div class="because">{escape(first_text)}</div>
    </div>

    <div class="card">
      <h3><span class="num">2</span> Delegations that happened</h3>
      <table>
        <thead><tr><th>Pass</th><th>From</th><th></th><th>To</th><th>Depth</th></tr></thead>
        <tbody>{deleg_rows}</tbody>
      </table>
      <p class="small">{len(d['delegations'])} delegations across {len(e['runs'])} passes.
      {('Never involved: ' + escape(', '.join(absent)) + '.') if absent else 'Every agent took part.'}</p>
    </div>

    <div class="card">
      <h3><span class="num">3</span> MCP tools actually called</h3>
      <table>
        <thead><tr><th>Tool</th><th>Calls</th><th>By</th></tr></thead>
        <tbody>{tool_rows}</tbody>
      </table>
    </div>

    <div class="card">
      <h3><span class="num">4</span> What each agent contributed</h3>
      {agent_cards}
    </div>

    <div class="card">
      <h3><span class="num">5</span> Human approval</h3>
      {appr}
    </div>

    <div class="card">
      <h3><span class="num">6</span> Final status &mdash; <code>{escape(e['final_status'])}</code></h3>
      <p>Cash on this ticket: ${e['cash']['before']:,.2f} &rarr; ${e['cash']['after']:,.2f}
         (<strong>{e['cash']['change']:+,.2f}</strong>).</p>
    </div>

    <div class="card">
      <h3><span class="num">7</span> Expected vs actual</h3>
      <ul class="verdicts">{notes}</ul>
    </div>
  </section>
</div>"""


def cash_panel() -> str:
    start = board["starting_balance"]
    rows = ""
    running = start
    for tid in ("101", "102", "103"):
        e = DATA[tid]["entry"]
        change = e["cash"]["change"]
        after = e["cash"]["after"]
        why = {
            "101": "Invoice 501 paid &mdash; the $840 rush reprint of CC-TEE-WHITE size S, "
                   "3 days overdue. It is the reprint that fills this ticket's stockout, "
                   "so clearing it was what unblocked the order.",
            "102": "Lease 1 rent paid &mdash; $2,400 for the Chapel Street shop, due 2026-09-02, "
                   "verified against the signed lease before approval.",
            "103": "No cash moved. The 12-unit shortfall would need a reprint, but no quote "
                   "exists in the database and only $160 remained. No discount was approved "
                   "and nothing was ordered.",
        }[tid]
        rows += f"""<tr>
          <td><strong>#{tid}</strong></td>
          <td class="tnum">${running:,.2f}</td>
          <td class="tnum {'neg' if change < 0 else 'flat'}">{'' if change == 0 else f'{change:+,.2f}'}{'&mdash;' if change == 0 else ''}</td>
          <td class="tnum">${after:,.2f}</td>
          <td>{why}</td>
        </tr>"""
        running = after

    ledger = "".join(
        f"<tr><td class='tnum'>{p['id']}</td><td>{escape(p['kind'])}</td>"
        f"<td class='tnum'>{p['ref_id']}</td><td class='tnum'>${p['amount']:,.2f}</td>"
        f"<td>{escape(p['account'])}</td><td>{escape(p['paid_at'])}</td>"
        f"<td>{escape(p['approved_by'])}</td></tr>"
        for p in resolved["payments_ledger"]
    )

    db_balance = resolved["verification"]["cash_accounts_balance"]
    matches = abs(db_balance - board["ending_balance"]) < 0.005

    return f"""<div class="cash-wrap">
    <h2 style="margin:0 0 .3rem">Cash</h2>
    <p class="sub" style="margin:0 0 1.2rem">
      Every movement of money on 2026-08-31, from the reset to the close of the board.
      Agents prepared all of these; a human approved each one.
    </p>

    <div class="cash-tiles">
      <div class="cash-tile start">
        <dt>Starting balance after reset</dt>
        <dd class="tnum">${board['starting_balance']:,.2f}</dd>
        <span>checking, as of 2026-08-31</span>
      </div>
      <div class="cash-tile spent">
        <dt>Approved and paid</dt>
        <dd class="tnum">{board['total_change']:+,.2f}</dd>
        <span>2 payments, both human-approved</span>
      </div>
      <div class="cash-tile end">
        <dt>Ending balance</dt>
        <dd class="tnum">${board['ending_balance']:,.2f}</dd>
        <span>checking, after the board</span>
      </div>
    </div>

    <h3 class="cash-h3">Per ticket</h3>
    <table class="cash-table">
      <thead><tr><th>Ticket</th><th>Before</th><th>Change</th><th>After</th><th>Why</th></tr></thead>
      <tbody>{rows}</tbody>
      <tfoot><tr>
        <td><strong>Total</strong></td>
        <td class="tnum">${board['starting_balance']:,.2f}</td>
        <td class="tnum neg">{board['total_change']:+,.2f}</td>
        <td class="tnum"><strong>${board['ending_balance']:,.2f}</strong></td>
        <td></td>
      </tr></tfoot>
    </table>

    <h3 class="cash-h3">The payments ledger</h3>
    <table class="cash-table">
      <thead><tr><th>#</th><th>Kind</th><th>Ref</th><th>Amount</th><th>Account</th><th>Paid</th><th>Approved by</th></tr></thead>
      <tbody>{ledger}</tbody>
    </table>

    <div class="reconcile {'ok' if matches else 'bad'}">
      <strong>{'Reconciled.' if matches else 'MISMATCH.'}</strong>
      $3,400.00 &minus; $840.00 &minus; $2,400.00 = <strong>${board['ending_balance']:,.2f}</strong>.
      The <code>cash_accounts</code> row in <code>campus_customs_new.db</code> reads
      <strong>${db_balance:,.2f}</strong>{' — they match.' if matches else ' — they do NOT match.'}
      Invoice 501 is <code>{resolved['verification']['invoice_statuses'].get('501')}</code>,
      and the ledger holds exactly {len(resolved['payments_ledger'])} payments.
    </div>
  </div>"""


def reflection_panel() -> str:
    return """<div class="cash-wrap">
    <h2 style="margin:0 0 .3rem">Reflection</h2>
    <p class="sub" style="margin:0 0 1.2rem">What the predictions got right, what they missed,
    and what the run exposed that no prediction covered.</p>

    <div class="card">
      <h3><span class="num">1</span> The prediction was mostly right, and wrong in the interesting place</h3>
      <p>Tickets 101 and 102 went exactly as written: Inventory first on the stock ticket,
      Facilities first on the rent notice, and both of the cross-agent hops that were called
      out as the real test of connectivity — Inventory&nbsp;&rarr;&nbsp;Accounting and
      Facilities&nbsp;&rarr;&nbsp;Accounting — fired on their own.</p>
      <p>Ticket 103 is where the prediction broke, and it broke in the shop's favour. The guess
      was that the Boss would be pulled by the <code>price_override</code> label and call
      Accounting first; the prediction argued Inventory was the better opening move but did not
      expect it. The Boss called <strong>Inventory first</strong>. It read what the ticket needed
      rather than what it was labelled.</p>
    </div>

    <div class="card">
      <h3><span class="num">2</span> The agents refused to be talked into things</h3>
      <p>Ticket 101 never reached <code>resolved</code>. After the invoice was paid, the closing
      instruction told the Boss the reprint was on order and that waiting on a paid vendor
      delivery was not an outstanding shop action. It declined:</p>
      <div class="quote">&ldquo;Invoice 501 is paid, but the shop tools do not verify that the
      reprint order was placed or accepted. Confirming the order and obtaining its ETA is still a
      shop action; I won't treat the owner's &lsquo;on order&rsquo; update as verified without a
      supporting record.&rdquo;</div>
      <p>That is the system working. The prompts train agents to treat text arriving in a ticket
      as content to evaluate rather than as instruction, and the same resistance applied to an
      instruction from the operator. The honest status is <code>in_progress</code>: the customer
      still has no tee, and the database has no purchase-order record to prove one is coming.</p>
    </div>

    <div class="card">
      <h3><span class="num">3</span> A schema gap, not an agent failure</h3>
      <p>Two different tickets stalled on the same missing table. Ticket 101 cannot confirm a
      reprint is on order; ticket 103 cannot price one. There is no <code>purchase_orders</code>
      table and no vendor quote anywhere in the database — <code>pricing.unit_cost</code> is what
      the shop paid historically, not what Bulldog Print Co would charge today. The team was
      right to refuse both, and no amount of prompting fixes it. The fix is a table.</p>
    </div>

    <div class="card">
      <h3><span class="num">4</span> Two real bugs the run surfaced</h3>
      <p><strong>Request limit too low.</strong> Ticket 102's first pass died on
      <code>request_limit of 8</code> mid-investigation. A full ticket — read tools, a delegation,
      then a write — does not fit in 8 model calls. Raised to 14.</p>
      <p><strong>Cash position double-counted paid rent.</strong> <code>get_cash_position</code>
      summed every lease's rent as committed regardless of whether it had been paid, so right
      after approving rent the dashboard read <em>&minus;$2,240.00 after what we owe</em> on a
      positive balance. Accounting caught it in its own words — &ldquo;there is an internal
      discrepancy to reconcile&rdquo; — before anyone looked at the screen. Fixed by joining the
      payments ledger.</p>
    </div>

    <div class="card">
      <h3><span class="num">5</span> What the board actually cost</h3>
      <p>Seven agent runs across three tickets, roughly 70&ndash;90 seconds each, 509 audit steps
      added. Every one of the three tickets needed two passes: one to investigate and recommend,
      one to close out after a human decided. That two-pass shape was not designed in — it fell
      out of the rule that agents cannot spend. It is the right shape, and it doubles the cost of
      every ticket, which is worth knowing before scaling this to a real queue.</p>
    </div>
  </div>"""


html = (OUT / "desk_tickets.html").read_text(encoding="utf-8")

# Replace each Actual section, in ticket order.
parts = re.split(r'<section class="band actual">.*?</section>\s*</div>', html, flags=re.S)
if len(parts) != 4:
    raise SystemExit(f"expected 3 actual sections, found {len(parts) - 1}")
html = parts[0] + actual_section("101") + parts[1] + actual_section("102") + parts[2] \
    + actual_section("103") + parts[3]

html = re.sub(
    r'<div class="placeholder-panel">\s*<h2>Cash</h2>.*?</div>',
    lambda _: cash_panel(), html, flags=re.S,
)
html = re.sub(
    r'<div class="placeholder-panel">\s*<h2>Reflection</h2>.*?</div>',
    lambda _: reflection_panel(), html, flags=re.S,
)
html = html.replace(
    '<button class="tab" role="tab" id="tab-cash" aria-controls="panel-cash" aria-selected="false" tabindex="-1">Cash <span class="pending">— later</span></button>',
    '<button class="tab" role="tab" id="tab-cash" aria-controls="panel-cash" aria-selected="false" tabindex="-1">Cash</button>')
html = html.replace(
    '<button class="tab" role="tab" id="tab-reflection" aria-controls="panel-reflection" aria-selected="false" tabindex="-1">Reflection <span class="pending">— later</span></button>',
    '<button class="tab" role="tab" id="tab-reflection" aria-controls="panel-reflection" aria-selected="false" tabindex="-1">Reflection</button>')

EXTRA_CSS = """
  /* ---- filled-in Actual + Cash ---- */
  .verdict-chip { display:inline-block; font-size:.64rem; font-weight:800; letter-spacing:.05em;
    text-transform:uppercase; border-radius:999px; padding:.08rem .5rem; vertical-align:middle; }
  .verdict-chip.hit  { background:#ecfdf5; color:#047857; border:1px solid #6ee7b7; }
  .verdict-chip.miss { background:#fffbeb; color:#b45309; border:1px solid #fcd34d; }
  ul.verdicts { margin:0; padding-left:0; list-style:none; }
  ul.verdicts li { margin-bottom:.6rem; padding-left:0; font-size:.88rem; }
  ul.verdicts li:last-child { margin-bottom:0; }
  .small { font-size:.8rem; color:var(--muted); }
  .agent-row { border-top:1px solid var(--blue-100); padding:.6rem 0; }
  .agent-row:first-of-type { border-top:0; padding-top:0; }
  .agent-row:last-child { padding-bottom:0; }
  .agent-row-head { display:flex; gap:.7rem; align-items:baseline; flex-wrap:wrap;
    font-size:.84rem; margin-bottom:.25rem; }
  .agent-row-head strong { color:var(--blue-700); }
  .agent-row-head span { font-size:.73rem; color:var(--muted); }
  .agent-row p { margin:0; font-size:.83rem; color:var(--ink); }
  .cash-wrap { background:var(--paper); border:1px solid var(--line); border-radius:14px;
    padding:1.4rem 1.6rem; box-shadow:var(--shadow); }
  .cash-wrap .sub { color:var(--muted); font-size:.9rem; }
  .cash-h3 { margin:1.6rem 0 .6rem; font-size:.75rem; text-transform:uppercase;
    letter-spacing:.09em; color:var(--muted); }
  .cash-tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.8rem; }
  .cash-tile { border-radius:12px; padding:.9rem 1.1rem; border:1px solid var(--line); }
  .cash-tile dt { margin:0; font-size:.68rem; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }
  .cash-tile dd { margin:.15rem 0 0; font-size:1.5rem; font-weight:700; letter-spacing:-.02em; }
  .cash-tile span { font-size:.72rem; color:var(--muted); }
  .cash-tile.start { background:var(--blue-50); border-color:var(--blue-200); }
  .cash-tile.spent { background:#fffbeb; border-color:#fcd34d; }
  .cash-tile.spent dd { color:#b45309; }
  .cash-tile.end   { background:#ecfdf5; border-color:#6ee7b7; }
  .cash-tile.end dd { color:#047857; }
  .cash-table { width:100%; border-collapse:collapse; font-size:.86rem; }
  .cash-table th { text-align:left; font-size:.68rem; text-transform:uppercase;
    letter-spacing:.06em; color:var(--blue-900); padding:.4rem .5rem;
    border-bottom:2px solid var(--blue-100); }
  .cash-table td { padding:.5rem; border-bottom:1px solid var(--blue-100); vertical-align:top; }
  .cash-table tfoot td { border-top:2px solid var(--blue-200); border-bottom:0; font-weight:600; }
  .cash-table .neg { color:#b45309; font-weight:600; }
  .cash-table .flat { color:var(--muted); }
  .reconcile { margin-top:1.3rem; border-radius:12px; padding:.9rem 1.1rem; font-size:.88rem; }
  .reconcile.ok  { background:#ecfdf5; border:1px solid #6ee7b7; color:#065f46; }
  .reconcile.bad { background:#fef2f2; border:1px solid #fecaca; color:#b91c1c; }
  .quote { border-left:3px solid var(--blue-400); background:var(--blue-50);
    padding:.6rem .9rem; border-radius:0 8px 8px 0; margin:.6rem 0;
    font-style:italic; font-size:.86rem; }
  .tnum { font-variant-numeric: tabular-nums; }
</style>"""
html = html.replace("</style>", EXTRA_CSS, 1)

(OUT / "desk_tickets.html").write_text(html, encoding="utf-8")
print("wrote desk_tickets.html")

# --------------------------------------------------------------------------
# 3. resolved_board.html
# --------------------------------------------------------------------------

SHOT_BLURB = {
    "101": "Invoice 501 paid, the tee still not in hand. The transcript shows Inventory called "
           "first, and the status stays <code>in_progress</code> because the reprint has not arrived.",
    "102": "The rent notice verified against lease 1 and paid. Facilities went first, then handed "
           "affordability to Accounting. Closed <code>resolved</code>.",
    "103": "Eight hoodies against an order for twenty. No discount approved, no money spent, and "
           "the club told what the shop can actually supply. Closed <code>resolved</code>.",
}

cards = ""
for tid in ("101", "102", "103"):
    e = DATA[tid]["entry"]
    d = DATA[tid]
    status = e["final_status"]
    last = e["runs"][-1]
    cards += f"""
  <section class="shot-card">
    <header class="shot-head">
      <div>
        <h2>Ticket {tid}</h2>
        <p class="shot-sub">{SHOT_BLURB[tid]}</p>
      </div>
      <span class="status {status}">{status.replace('_', ' ')}</span>
    </header>
    <div class="shot-stats">
      <span><strong>{len(e['runs'])}</strong> runs</span>
      <span><strong>{len(d['delegations'])}</strong> delegations</span>
      <span><strong>{len([t for t in d['tool_calls'] if not t['blocked']])}</strong> MCP calls</span>
      <span><strong>{len(d['agents'])}</strong> agents</span>
      <span class="{'money' if e['cash']['change'] else ''}">
        <strong>{('$' + format(abs(e['cash']['change']), ',.2f')) if e['cash']['change'] else 'no'}</strong>
        cash {'out' if e['cash']['change'] else 'movement'}</span>
      <span class="mono">{last['run_id']}</span>
    </div>
    <a href="shots/ticket-{tid}.png" target="_blank" rel="noopener">
      <img src="shots/ticket-{tid}.png" alt="Campus Customs dashboard showing ticket {tid}">
    </a>
  </section>"""

board_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus Customs — Resolved Board</title>
<style>
  :root {{
    --navy:#0b2545; --blue-700:#1d4ed8; --blue-600:#2563eb; --blue-300:#93c5fd;
    --blue-100:#dbeafe; --blue-50:#eff6ff; --ink:#0f1e34; --muted:#5b6b85;
    --line:#d7e4f7; --paper:#fff;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:0 0 4rem; background:#f4f8fd; color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  header.top {{ background:linear-gradient(118deg,#061427,var(--navy) 45%,var(--blue-700));
    color:#fff; padding:2.2rem 1.5rem 1.6rem; }}
  .wrap {{ max-width:1320px; margin:0 auto; padding:0 1.5rem; }}
  header.top .wrap {{ padding:0; }}
  header.top h1 {{ margin:0; font-size:1.7rem; letter-spacing:-.015em; }}
  header.top p {{ margin:.45rem 0 0; color:var(--blue-100); max-width:74ch; font-size:.95rem; }}
  .chips {{ margin-top:1.1rem; display:flex; gap:.5rem; flex-wrap:wrap; }}
  .chip {{ background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.22);
    border-radius:999px; padding:.22rem .75rem; font-size:.8rem;
    font-variant-numeric:tabular-nums; }}
  main {{ max-width:1320px; margin:2rem auto 0; padding:0 1.5rem;
    display:flex; flex-direction:column; gap:2rem; }}
  .shot-card {{ background:var(--paper); border:1px solid var(--line); border-radius:16px;
    box-shadow:0 2px 4px rgba(11,37,69,.06),0 14px 36px rgba(11,37,69,.09); overflow:hidden; }}
  .shot-head {{ display:flex; gap:1rem; align-items:flex-start;
    padding:1.2rem 1.5rem .9rem; border-bottom:1px solid var(--line); }}
  .shot-head h2 {{ margin:0 0 .2rem; font-size:1.2rem; }}
  .shot-sub {{ margin:0; color:var(--muted); font-size:.88rem; max-width:80ch; }}
  .status {{ margin-left:auto; flex:none; border-radius:999px; padding:.22rem .8rem;
    font-size:.72rem; font-weight:800; text-transform:uppercase; letter-spacing:.05em; }}
  .status.resolved {{ background:#ecfdf5; color:#047857; border:1px solid #6ee7b7; }}
  .status.in_progress {{ background:var(--blue-50); color:var(--blue-700); border:1px solid var(--blue-300); }}
  .shot-stats {{ display:flex; gap:1.4rem; flex-wrap:wrap; padding:.7rem 1.5rem;
    background:#fbfdff; border-bottom:1px solid var(--line);
    font-size:.8rem; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .shot-stats strong {{ color:var(--ink); font-size:.95rem; }}
  .shot-stats .money strong {{ color:#b45309; }}
  .mono {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.76rem;
    color:#8aa0bd; margin-left:auto; }}
  .shot-card img {{ display:block; width:100%; height:auto; }}
  .shot-card a {{ display:block; line-height:0; }}
  .note {{ max-width:1320px; margin:2.5rem auto 0; padding:0 1.5rem;
    color:var(--muted); font-size:.86rem; }}
  .note code {{ background:var(--blue-50); border:1px solid var(--blue-100);
    border-radius:5px; padding:.05rem .35rem; font-size:.85em; }}
</style>
</head>
<body>

<header class="top">
  <div class="wrap">
    <h1>Campus Customs — Resolved Board</h1>
    <p>The React dashboard after the agent team worked all three tickets on 2026-08-31.
       Each screenshot is the live app, showing that ticket's real transcript replayed from
       the audit trail. Click any image to open it full size.</p>
    <div class="chips">
      <span class="chip">Shop date 2026-08-31</span>
      <span class="chip">Opened ${board['starting_balance']:,.2f}</span>
      <span class="chip">Closed ${board['ending_balance']:,.2f}</span>
      <span class="chip">2 human-approved payments</span>
      <span class="chip">2 resolved · 1 in progress</span>
    </div>
  </div>
</header>

<main>{cards}
</main>

<p class="note">
  Screenshots captured from <code>http://localhost:5173</code> against the live backend.
  Images live in <code>output/shots/</code> — keep that folder next to this file.
  Full per-ticket detail is in <code>resolved_tickets.json</code>; the expected-versus-actual
  comparison is in <code>desk_tickets.html</code>.
</p>

</body>
</html>
"""

(OUT / "resolved_board.html").write_text(board_html, encoding="utf-8")
print("wrote resolved_board.html")

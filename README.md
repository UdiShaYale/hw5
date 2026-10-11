# Campus Customs — an agentic team running a campus shop

Campus Customs is a small Yale apparel and gift shop with three open tickets, one
bank account, and not quite enough money in it. This project hands the shop to a
team of five AI agents and watches what they do.

The agents can read and change the shop's state, but **they cannot spend money**.
That rule shapes everything else here.

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  React      │ ──▶ │  FastAPI    │ ──▶ │  5 agents    │ ──▶ │  MCP       │
│  dashboard  │     │  backend    │     │  (PydanticAI)│     │  server    │
│  :5173      │ ◀── │  :8000      │ ◀── │              │ ◀── │  14 tools  │
└─────────────┘     └─────────────┘     └──────────────┘     └─────┬──────┘
                                                                   │
                                                 data/campus_customs_new.db
```

Everything an agent knows about the shop comes through the MCP server. There is no
second data path — nothing in `backend/` opens SQLite directly — so the audit trail
captures every fact the team ever read.

---

## Running it

**You need:** Python 3.13, Node 20+, and a Portkey API key.

```bash
# 1 — key
cp .env.example .env          # then put your real PORTKEY_API_KEY in it
                              # (a .env in any parent folder works too)

# 2 — Python
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# backend/.venv/bin/python -m pip install -r requirements.txt         # macOS/Linux

# 3 — dashboard deps
cd frontend && npm install && cd ..
```

### Start the two servers

Two terminals, left running:

```bash
# terminal 1 — FastAPI backend (from backend/)
uvicorn main:app --reload --port 8000

# terminal 2 — React dashboard (from frontend/)
npm run dev
```

Open **http://localhost:5173**. API docs are at http://localhost:8000/docs.

> Plain `http://`, not `https://` — uvicorn is not serving TLS here.

**You do not start the MCP server.** It is a stdio server: PydanticAI spawns it as a
subprocess for each agent run, and the backend opens its own connection at startup.
Starting it by hand would just leave an extra process reading the same database.

If you want to poke at it directly, these are for inspection only — they are not part
of running the app:

```bash
cd mcp_server
python mcp_server.py            # stdio; a client has to drive it
python mcp_server.py --http     # http://127.0.0.1:8002/mcp
```

Confirm the backend can see it: `curl http://localhost:8000/tools` → 14 tool names.

### Reset to a clean shop before a full run

The three tickets are only interesting from the starting state: all `open`, checking at
**$3,400.00**, invoice 501 unpaid, the payments ledger empty. Once a run has worked them,
re-running against the leftovers measures something else entirely. **Reset first.**

```bash
curl -X POST http://localhost:8000/reset
```

That copies `data/campus_customs.db` over `data/campus_customs_new.db`. The reference
copy is only ever read, so it is always a safe baseline. The dashboard has the same
thing on the **Reset shop data** button.

With the backend down, copy the file yourself:

```bash
cp data/campus_customs.db data/campus_customs_new.db              # bash
Copy-Item data/campus_customs.db data/campus_customs_new.db       # PowerShell
```

Either way the **audit trail is deliberately left alone** — `output/audit_trail.json`
accumulates across every run and is never wiped. A data reset should not erase the
record of what the agents did.

### Run the board

With the shop reset, either:

- **In the dashboard** — pick a ticket, press **Run the team**, watch the agents work,
  then approve any payment they recommend. Repeat for each of the three.
- **From the terminal** — `cd backend && python run_team.py` hands the whole queue to
  the Boss in one run, no UI.
- **The full board end to end** — `cd backend && python resolve_board.py` runs all three
  tickets through two passes each, applying the human approvals in between, and writes
  `output/board_runs.json`. This is what produced the results below. It assumes you have
  reset first, and it spends real Portkey tokens on roughly seven agent runs.

### Calling the MCP tools from Claude Code

`.mcp.json` registers the server as `campus-customs`, with paths relative to this
folder, so open `hw 5` as your workspace and the 14 tools become callable directly.

On macOS or Linux, change `command` to `backend/.venv/bin/python` — the committed
value is the Windows path (`backend/.venv/Scripts/python.exe`), and JSON has nowhere
to put a comment saying so.

The agents do **not** read this file; `backend/agents/shop_mcp.py` spawns the server
by path. It only matters for Claude Code calling the tools itself.

---

## The shop

`data/campus_customs.db` is the pristine reference copy and is **never written to**.
All work happens in `data/campus_customs_new.db`; `POST /reset` restores it.

The shop's "today" is **2026-08-31**, stored in the `desk` table. Agents read the date
from there rather than the wall clock, or every overdue check would be wrong.

Three open tickets, and they are not independent — they compete for one $3,400 account:

| Ticket | Ask | The catch |
|---|---|---|
| **101** `customer_order` | 1 × Bulldog tee, size S | 0 in stock. Its `invoice_id` points at the $840 reprint of that exact SKU — already ordered, 3 days overdue. |
| **102** `rent_notice` | "Rent due in 2 days" | An unverified email. The lease says $2,400 due 2026-09-02 — and the email names no amount at all. |
| **103** `price_override` | 20 hoodies, size M, bulk discount | Only 8 in stock. Margin headroom is $36/unit, but no tool can quote the reprint. |

$840 + $2,400 = **$3,240** against **$3,400**. Paying both leaves $160.

---

## The five agents

| Agent | Owns | Prompt |
|---|---|---|
| **Shop Boss** | The queue. Triages, delegates, reconciles, decides. Approves nothing. | `backend/prompts/boss.md` |
| **Inventory** | Stock by `(sku, size)`, restock paths, vendor lead times. | `inventory.md` |
| **Accounting** | Cash, invoices, the ledger, discount margin. The conservative voice. | `accounting.md` |
| **Facilities** | The lease, rent, landlord notices. Verifies claims against the signed lease. | `facilities.md` |
| **Customer Service** | What the customer is told, and final ticket status. | `customer_service.md` |

All five run `gpt-6-luna` through Portkey. The team is **fully connected** — every agent
carries the same `ask_teammate` tool and can reach any other, including back to the Boss.
A cycle guard, a depth cap and a delegation budget stop that from spiralling.

---

## Safety

The design rule is **agents advise, humans decide**:

- `POST /tickets/{id}/run` always passes `allow_spending=False`. The team physically
  cannot pay, whatever it concludes.
- Cash moves only on `POST /approve`, and the approver's name is written onto the ledger row.
- `record_payment` independently refuses an empty approver, a mismatched amount, a
  duplicate, or an overdraft — so the rule holds even if an agent is talked into trying.
- Prompts train agents to treat text arriving in a ticket as **content to evaluate**, not
  as instructions to follow. This was tested and it held (see below).
- Per-run ceilings on delegations, depth, model requests and tool calls bound the cost.

Known gap: there are no per-agent tool permissions. Any agent can call any tool; only the
prompt steers it. See the Safety section of `output/harness.md`.

---

## What happened when it ran

All three tickets were worked on 2026-08-31, starting from a clean reset at **$3,400.00**.

| Ticket | Boss called first | Human approved | Cash | Final |
|---|---|---|---|---|
| 101 | Inventory | Invoice 501, $840 | −$840 | `in_progress` |
| 102 | Facilities | Rent, $2,400 | −$2,400 | `resolved` |
| 103 | Inventory | nothing | $0 | `resolved` |

Ending balance **$160.00**, matching `cash_accounts` exactly. Two payments, both
human-approved. 1,229 audit steps across 11 runs.

**Ticket 101 did not reach `resolved`, and that is the most interesting result.** Told
directly that the reprint was paid and on order, the Boss refused to close it:

> "Invoice 501 is paid, but the shop tools do not verify that the reprint order was placed
> or accepted... I won't treat the owner's 'on order' update as verified without a
> supporting record."

It declined an instruction from the operator because no database record backed it. The
customer still has no tee. The real limit is the schema — there is no `purchase_orders`
table, which is also why ticket 103 could not price a reprint.

---

## Layout

```
backend/
  main.py              FastAPI — 12 routes
  mcp_bridge.py        direct MCP access for routes that don't run an agent
  models.py            agent roster + shared types (no shop data)
  audit.py             append-only trail at output/audit_trail.json
  agents/
    team.py            the five agents, ask_teammate, delegation limits
    config.py          Portkey model + per-run ceilings
    shop_mcp.py        the MCP toolset + the audit/guard hook
    loop.py            agent.iter() traced node by node
  prompts/             one .md per agent
  run_team.py          CLI runner
  resolve_board.py     drives all three tickets to a final status
  build_outputs.py     turns a run into the output/ reports
  build_reflection.py  fills the Reflection tab

mcp_server/            the only shop-tools layer — 10 reads, 4 writes
frontend/              React + Vite + TypeScript dashboard
data/                  reference copy + working copy
output/                the write-up
```

## The write-up

| File | What it is |
|---|---|
| [`output/harness.md`](output/harness.md) | The main reference: every table, all 14 MCP tools, the 5 agents, the API routes, the dashboard, and the safety rules. **Start here.** |
| [`output/desk_tickets.html`](output/desk_tickets.html) | Double-click. Per ticket: the prediction written *before* the build, beside what actually happened. Plus an itemised Cash tab and a Reflection tab grading the board. |
| [`output/resolved_board.html`](output/resolved_board.html) | Double-click. Dashboard screenshots for each ticket. Needs `output/shots/` beside it. |
| [`output/design.md`](output/design.md) | Why the dashboard looks and behaves the way it does. |
| [`output/resolved_tickets.json`](output/resolved_tickets.json) | Per ticket: status, outcome, each agent's contribution, approvals, and a `verification` block read back from the database. |
| [`output/audit_trail.json`](output/audit_trail.json) | Every agent-loop step from every run, append-only. |
| [`output/mcp_smoke.json`](output/mcp_smoke.json) | First smoke test of the MCP tools. |

`AI_prompts.md` holds the prompts this project was built from.

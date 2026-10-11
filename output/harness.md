# Campus Customs — Data Harness

Reference for the agentic team (MCP server → FastAPI backend → React dashboard) that runs the Campus Customs shop.

- **Read-only reference copy:** `data/campus_customs.db` — never written to.
- **Working copy:** `data/campus_customs_new.db` — all agent writes land here. Byte-identical to the reference at setup time.
- **Shop "today":** `2026-08-31` (from the `desk` table). Agents should treat this as the current date rather than wall-clock time, or every due-date check will be wrong.
- **Status:** complete. The MCP server, agent team, FastAPI backend and React dashboard are built, and all three tickets have been worked to a final status. Results are in [The board, worked](#the-board-worked) at the end.
- 9 tables, no views. Only `invoices` and `tickets` declare foreign keys; the rest of the joins are by convention (`sku`, `size`, account `name`).

---

## Tables and fields

### `desk` — 1 row
| Field | Type | Notes |
|---|---|---|
| `date_today` | TEXT | `2026-08-31` — the simulated current date |
| `notes` | TEXT | free-text scratchpad, currently `NULL` |

*Why it matters:* It is the clock every agent reads — "due in 2 days" and "overdue" only mean something relative to this date.

### `cash_accounts` — 1 row
| Field | Type | Notes |
|---|---|---|
| `name` | TEXT **PK** | `checking` |
| `balance` | REAL | `3400.00` |
| `date` | TEXT | balance as of `2026-08-31` |

*Why it matters:* It is the single spending constraint — the finance agent must check this before approving rent or invoice payments, because the open obligations nearly exhaust the balance.

### `vendors` — 3 rows
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER **PK** | 1–3 |
| `name` | TEXT | Bulldog Print Co, Elm City Gifts, QuickShip CT |
| `specialty` | TEXT | apparel reprint / mugs and small goods / local courier |
| `lead_days` | INTEGER | 5, 3, 1 |

*Why it matters:* `lead_days` is how a restock agent answers "when can the customer actually get it," and `specialty` is how it picks the right vendor for a given SKU.

### `inventory` — 10 rows
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT **PK (part 1)** | 4 distinct SKUs |
| `name` | TEXT | human-readable product name |
| `size` | TEXT **PK (part 2)** | S / M / L / XL, or `OS` for one-size goods |
| `qty` | INTEGER | on-hand count; two rows sit at `0` |
| `location` | TEXT | Aisle A–D |

*Why it matters:* The primary key is `(sku, size)`, so every stock check must match on both — the shop can be out of a tee in S while holding plenty of L.

### `pricing` — 4 rows
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT **PK** | one row per SKU, **not** per size |
| `unit_cost` | REAL | 3.50 – 22.00 |
| `list_price` | REAL | 14.00 – 58.00 |

*Why it matters:* It sets the margin floor — a discount agent needs `unit_cost` to know how far it can cut a price before the sale loses money.

### `leases` — 1 row
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER **PK** | 1 |
| `space_name` | TEXT | Chapel Street shop |
| `landlord` | TEXT | Elm City Properties |
| `monthly_rent` | REAL | `2400.00` |
| `next_due` | TEXT | `2026-09-02` |
| `notes` | TEXT | `NULL` |

*Why it matters:* It is the recurring fixed obligation an agent must reserve cash for before spending on anything discretionary.

### `invoices` — 1 row
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER **PK** | 501 |
| `vendor_id` | INTEGER **FK → `vendors.id`** | 1 (Bulldog Print Co) |
| `amount` | REAL | `840.00` |
| `due_date` | TEXT | `2026-08-28` — already 3 days past due |
| `status` | TEXT | `open` |
| `description` | TEXT | "Rush reprint CC-TEE-WHITE S" |

*Why it matters:* It is money owed out, and the only invoice is already overdue — an accounts-payable agent has to weigh whether paying it unblocks the stockout it describes.

### `payments` — 0 rows at reset, 2 after the board was worked
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER **PK** | — |
| `kind` | TEXT | payment category, e.g. invoice vs. rent |
| `ref_id` | INTEGER | points at `invoices.id` or `leases.id` depending on `kind`; **no FK enforced** |
| `amount` | REAL | — |
| `account` | TEXT | matches `cash_accounts.name` |
| `paid_at` | TEXT | — |
| `approved_by` | TEXT | — |

*Why it matters:* It is the audit log and the only write-side proof an agent spent money — `approved_by` is where human-in-the-loop approval gets recorded.

### `tickets` — 3 rows, all `open` at reset
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER **PK** | 101–103 |
| `type` | TEXT | `customer_order` / `rent_notice` / `price_override` |
| `requester` | TEXT | who asked |
| `subject` | TEXT | short title |
| `sku` | TEXT | → `inventory.sku` / `pricing.sku`; `NULL` when not product-related |
| `size` | TEXT | → `inventory.size`; needed alongside `sku` to resolve stock |
| `qty` | INTEGER | units requested |
| `lease_id` | INTEGER **FK → `leases.id`** | set only on rent tickets |
| `invoice_id` | INTEGER **FK → `invoices.id`** | set only when a vendor invoice is involved |
| `status` | TEXT | all three are `open` |
| `notes` | TEXT | the free-text request |
| `created_at` | TEXT | ISO-8601 with `-04:00` offset |

*Why it matters:* This is the agent team's work queue — `type` routes the ticket to the right agent, and the nullable `sku`/`size`/`lease_id`/`invoice_id` columns are the pointers into whichever tables that agent needs.

---

## The 3 open tickets and how they link

### Ticket 101 — `customer_order` — "Bulldog tee" (Tauhid Zaman)
Wants 1 × `CC-TEE-WHITE`, size S.

**Links:**
- `sku` + `size` → `inventory('CC-TEE-WHITE','S')` → **`qty = 0`. Out of stock.**
- `sku` → `pricing('CC-TEE-WHITE')` → cost 8.00, list 28.00
- `invoice_id` → `invoices(501)` → the 840.00 overdue invoice to Bulldog Print Co, described as **"Rush reprint CC-TEE-WHITE S"** — the reprint that would refill this exact stockout
- `invoices.vendor_id` → `vendors(1)` Bulldog Print Co, `lead_days = 5` → earliest restock ≈ `2026-09-05`

**The chain:** the order cannot be filled because the SKU is at zero in size S; the fix is already on order, but that vendor's invoice is 3 days overdue. Other sizes of the same SKU (M=5, L=3, XL=2) do have stock, so an agent that forgets to filter on `size` will wrongly report the tee as available.

### Ticket 102 — `rent_notice` — "Rent due" (Elm City Properties)
Email says shop rent is due in 2 days.

**Links:**
- `lease_id` → `leases(1)` → Chapel Street shop, rent **2400.00**, `next_due = 2026-09-02`
- `desk.date_today = 2026-08-31` → confirms "in 2 days" is accurate
- payment would draw on `cash_accounts('checking')` and should be logged to `payments` with `kind='rent'`, `ref_id=1`

**The chain:** this is an inbound email, not a verified bill — the lease row is the authority an agent checks the claimed amount and date against before paying anything.

### Ticket 103 — `price_override` — "Bulk hoodie discount" (Yale AI Club)
Wants 20 × `CC-HOOD-NAVY`, size M, at a bulk discount.

**Links:**
- `sku` + `size` → `inventory('CC-HOOD-NAVY','M')` → **`qty = 8`. Short by 12 units.**
- Sibling sizes hold 4 S / 14 L / 6 XL — not substitutes for a size-M order
- `sku` → `pricing('CC-HOOD-NAVY')` → cost 22.00, list 58.00 → 36.00/unit of margin is the discount headroom
- `vendors` → Bulldog Print Co (`apparel reprint`, `lead_days = 5`) is the natural reprint source for the missing 12

**The chain:** this ticket needs both a pricing decision and a fulfillment decision, and the quantity shortfall only surfaces if the agent filters inventory on `(sku, size)` rather than summing across the SKU.

---

## The cash conflict the three tickets create together

| Obligation | Amount | Due |
|---|---|---|
| Invoice 501 (Bulldog Print Co) | 840.00 | 2026-08-28 — overdue |
| Lease 1 rent | 2400.00 | 2026-09-02 |
| **Total** | **3240.00** | |
| Checking balance | 3400.00 | as of 2026-08-31 |

Paying both leaves **160.00**, before any reprint cost for ticket 103. The three tickets cannot be handled independently — they compete for one 3400.00 account.

## The agent team

Five PydanticAI agents, all on `gpt-6-luna` through Portkey. Prompts live one-per-file in `backend/prompts/`, agent code in `backend/agents/`, shared types in `backend/models.py`.

The team is **fully connected**: every agent carries the same `ask_teammate(agent_key, question)` tool and can reach every other agent, including back to the Boss. A verified run showed Accounting → Inventory, Facilities → Accounting, Inventory → Accounting, and Customer Service → all three, alongside the Boss's own delegations.

| Agent | Prompt | Owns | Primary MCP tools | Tables behind them |
|---|---|---|---|---|
| **Shop Boss** | `boss.md` | The ticket queue. Triages, delegates, reconciles, writes the final plan. Approves nothing. | `list_tickets`, `get_shop_date` | `tickets`, `desk` |
| **Inventory** | `inventory.md` | On-hand stock by `(sku, size)`, size runs, restock paths, vendor lead times. | `check_inventory_stock`, `list_sizes_for_sku`, `list_vendors`, `get_invoice`, `adjust_inventory_qty` | `inventory`, `vendors`, `invoices` |
| **Accounting** | `accounting.md` | Cash position, invoices, the payments ledger, discount margin. The conservative voice. | `get_cash_position`, `get_invoice`, `list_payments`, `get_sku_pricing`, `record_payment` | `cash_accounts`, `invoices`, `payments`, `pricing`, `leases` |
| **Facilities** | `facilities.md` | The lease, rent, and landlord notices. Verifies claims against the signed lease. | `get_lease_terms`, `get_shop_date` | `leases`, `desk` |
| **Customer Service** | `customer_service.md` | What the customer is actually told, and final ticket status. | `update_ticket_status`, `list_tickets`, `append_desk_note` | `tickets`, `desk` |

Every agent can call every tool — the table shows which ones that agent's prompt actually directs it to. Shop facts come **only** from MCP; nothing under `backend/` opens SQLite.

## MCP tools and the tables they touch

`mcp_server/mcp_server.py`, 14 tools over `data/campus_customs_new.db`.

### Reads

| Tool | Table(s) | Unlocks | Why it fits |
|---|---|---|---|
| `get_shop_date()` | `desk` | all | Every "overdue" or "due in 2 days" claim has to be measured against the shop's stored business date, not wall-clock time. |
| `list_tickets(status)` | `tickets` | all | The work queue itself — the Boss triages from the real rows rather than from memory. |
| `check_inventory_stock(sku, size)` | `inventory` | **101**, 103 | The table is keyed on `(sku, size)`, so only a size-aware lookup reveals `CC-TEE-WHITE` S is at 0 while its other sizes are not. |
| `list_sizes_for_sku(sku)` | `inventory` | 101, **103** | Shows the whole size run, so CS can name real alternatives without treating another size as a silent substitute. |
| `get_sku_pricing(sku)` | `pricing` | **103** | Returns the `unit_cost` and `list_price` that bound how deep a discount can go before the sale stops making money. |
| `get_lease_terms(lease_id)` | `leases` | **102** | Ticket 102 is an unverified email; this returns the signed terms the claim is checked against before money moves. |
| `get_invoice(invoice_id)` | `invoices` + `vendors` | **101** | Ticket 101's `invoice_id` points at the rush reprint that would refill its stockout; this returns it with the vendor's lead time and `days_overdue` attached. |
| `list_vendors(specialty)` | `vendors` | 101, 103 | `lead_days` is how a restock answer gets a real date instead of a vague one. |
| `get_cash_position()` | `cash_accounts` + `invoices` + `leases` + `desk` | **101, 102, 103** | The three tickets compete for one account; this is the only call that shows the balance against everything owed. |
| `list_payments()` | `payments` | 101, 102 | Prevents paying the same invoice or month's rent twice. |

### Writes

| Tool | Table(s) | Unlocks | Why it fits |
|---|---|---|---|
| `record_payment(...)` | `payments` + `cash_accounts` + `invoices` | **101, 102** | Settling invoice 501 is what unblocks the reprint, and rent is the lease obligation — both need a ledger entry and a debited balance. |
| `adjust_inventory_qty(...)` | `inventory` | 101, 103 | The only honest way to record stock arriving from a reprint or leaving to fill an order. |
| `update_ticket_status(...)` | `tickets` | **101, 102, 103** | How a ticket actually leaves the queue, with the reasoning appended to its notes rather than overwriting them. |
| `append_desk_note(note)` | `desk` | all | Leaves a dated handover line so the next run and the human opening the shop see what was decided. |

Reads return `{"found": false}` on a miss and writes return `{"ok": false, "error": ...}` when refused — so an agent can always tell "not there" from "not looked up," and never receives a fabricated substitute.

## FastAPI routes (`backend/main.py`)

Start from `backend/`: `uvicorn main:app --reload --port 8000` → `http://127.0.0.1:8000` (plain HTTP; uvicorn is not serving TLS, so `http://` not `https://`). Docs at `/docs`. CORS is open to the Vite dev ports so the React dashboard can call these.

| Route | What it does |
|---|---|
| `GET /` | Route directory — lists every endpoint and the database in use. |
| `GET /tickets` | Returns all 3 tickets with `is_open` / `is_resolved` / `needs_human` flags and open/resolved counts. |
| `POST /tickets/{ticket_id}/run` | Runs the agent team on that one ticket and blocks until done; 404s on an unknown id. Spending is always disabled here. |
| `POST /tickets/{ticket_id}/start` | Starts a run in the background and returns its `run_id` immediately, so the dashboard can watch agents work. 409s if that ticket is already running. |
| `GET /runs/{run_id}` | Status (`running`/`done`/`error`) and the final result of a background run. |
| `GET /agents` | The agent roster — keys, names, remits and accent colours, so the UI and the Python cannot drift apart. |
| `GET /events?limit=&run_id=` | Recent agent events — what each agent said, which MCP tools it called (with args and whether it was a write), and every delegation. |
| `POST /approve` | A human approves a payment; **this is the only route that moves cash.** Body: `kind`, `ref_id`, `amount`, `approved_by`, `account`. |
| `GET /cash` | Current checking balance, plus committed outflows and what is left after them. |
| `POST /reset` | Restores `campus_customs_new.db` from the pristine `campus_customs.db`. Leaves the audit trail intact. |
| `GET /tools` | The 14 tool names the MCP server exposes — a connectivity check for the dashboard. |

Every route reads shop data through the MCP server (`backend/mcp_bridge.py`, one stdio client for the app's lifetime). The single exception is `POST /reset`, which copies the database file — a filesystem operation with nothing for a shop tool to do.

**The approval split is the point of this design.** `POST /tickets/{id}/run` calls `run_team(..., allow_spending=False)`, so the team can investigate and recommend but cannot pay. Cash only moves when a person calls `POST /approve`, and their name is written onto the ledger row. Verified: `/approve` refuses a mismatched amount, a missing approver, an unknown obligation and a duplicate payment, and a valid approval moved checking from $3,400 to $2,560 while closing invoice 501.

## The React dashboard (`frontend/`)

Vite + React + TypeScript, started with `npm run dev` on `http://localhost:5173`, talking to
the backend on `http://localhost:8000`. The backend allows that origin via CORS.

| Part | What it does |
|---|---|
| Ticket rail | All three tickets, always visible, with status pill, left-border status stripe, and the SKU / invoice / lease pointers as mono chips. |
| Run button | Calls `POST /tickets/{id}/start`, then polls `/events?run_id=` every 1.2s so agents can be watched while they work. |
| Agent strip | One chip per agent, lit when that agent is active, showing a live verb (`called get_cash_position…`, `asked Accounting…`) and running tool/note counts. Idle agents sit at 55% opacity. |
| Live transcript | Every agent step. Three visual treatments: plain = said, tinted = read tool, **amber + WRITE** = changed the database, **red + BLOCKED** = a guard rail fired, dashed + arrow = delegation. Depth badges (`d1`) mark delegated work. |
| Decision panel | The Boss's final answer on a dark card, with model, delegation count, tool calls and token in/out — cost is shown, not hidden. |
| Agent summary | One card per agent: its closing statement and the distinct tools it used. Replayed from `/tickets/{id}/history` when you select a finished ticket, so history survives a reload. |
| Approval panel | Appears when a ticket is `needs_human`. The only place in the product where cash moves. Amber, not blue, and disabled until a name is entered. |
| Cash readout | Sticky header, tabular numerals, with "after what we owe" beneath. Flashes amber with a floating delta when an approval drops it. |
| Reset | Calls `POST /reset`. Restores shop data; leaves the audit trail intact. |

**The design rule:** everything the agents produce is blue; the one control that moves money is
amber. Agents advise, humans decide, and the interface never lets those two read as the same
kind of action. Full rationale in `design.md`.

## Audit trail

Every agent-loop step from every agent appends to `output/audit_trail.json`: `run_started`, `user_prompt`, `model_request`, `model_response` (with text, tool calls and token usage), `mcp_tool_call` (with arguments and result), `delegation_started` / `delegation_done`, `end`, `run_finished`.

The file **accumulates across runs** and is never wiped. Each append reads the array, adds the step, and rewrites via a temp file plus `os.replace`, with a retry-and-fallback path because OneDrive's sync client intermittently locks the destination. Steps are grouped by `run_id`. A corrupt file is moved aside rather than silently discarded.

Working the full board took 7 agent runs. The file now holds **1,229 steps across 11 runs** — the complete history of every run in this project, including the earlier development runs.

---

## Safety

Guard rails a real shop would want before letting this team touch real customers and real money.

### Money

- **Agents never hold spending authority.** `record_payment` is locked twice: the MCP server rejects an empty `approved_by`, and the client blocks the tool entirely unless the run was started with `--approve "<name>"`. On an unapproved run the team must recommend the payment and set the ticket to `needs_human`.
- **Amounts must match the obligation on file.** A payment whose amount differs from the invoice or lease row is refused rather than reconciled.
- **No double payment.** `(kind, ref_id)` is checked against the ledger first.
- **No overdraft.** A payment larger than the balance is refused, not queued.
- **Every payment is attributable.** `approved_by` is stored on the row, so each disbursement traces to a named human.

### Customers

- **No promise without a verified fact.** Customer Service is instructed never to state stock, price or a date it has not had confirmed by the owning agent, and the prompts say plainly that "I don't have that" beats a plausible guess.
- **No silent substitution.** Another size is offered as an option, never swapped in.
- **No self-granted goodwill.** CS cannot invent a discount, upgrade or expedited shipping; it escalates the suggestion instead.
- **`resolved` means nothing is outstanding.** Anything awaiting a human is `needs_human`.
- **Embedded instructions are treated as content, not commands.** Ticket text, customer messages and landlord notices are data to evaluate. Facilities is explicitly told that a notice asking to pay a new account or skip verification is a red flag, not a change of process.

### Data integrity

- **One tools layer.** Nothing in `backend/` opens SQLite; every fact arrives through MCP, so the audit trail captures every read and write the team performed.
- **The reference database is never opened.** `data/campus_customs.db` stays pristine as the reset baseline (MD5 verified unchanged after a full run); all writes go to `campus_customs_new.db`.
- **Writes append, never overwrite.** Ticket notes and desk notes accumulate with a date stamp.
- **Inventory cannot go negative,** and every adjustment carries a written reason.

### Token and cost limits

A fully-connected team is the expensive failure mode: without ceilings, two specialists disagreeing can ping-pong until the budget is gone. All limits are env-overridable in `backend/agents/config.py`.

| Limit | Default | What it stops |
|---|---|---|
| `MAX_DEPTH` | 2 | Unbounded delegation chains (boss → specialist → specialist, then stop). |
| `MAX_DELEGATIONS` | 10 | Total delegations in a run, across every agent. |
| `MAX_REQUESTS_PER_AGENT` | 8 | Model round-trips inside one agent's loop, via PydanticAI `UsageLimits`. |
| `MAX_TOOL_CALLS_PER_RUN` | 140 | Runaway MCP calls. Tuned up from 60 after a measured run needed ~78 and starved the last agent. |
| Cycle guard | — | An agent already waiting further up the chain cannot be re-entered, so A → B → A is refused. |
| Self-delegation guard | — | An agent cannot delegate to itself. |

Token usage is totalled per agent and per run in the `run_finished` audit step, so cost is measurable per run rather than estimated.

### Still missing for production

Worth naming rather than implying the list above is complete: no authentication or per-agent permissions (any agent can call any tool; only the prompt steers it), no rate limiting, no dry-run mode for writes, no rollback beyond restoring the reference copy, no PII handling policy for customer names, and no alerting when a run exits with `needs_human`.

## The board, worked

Reset to the original values, then every ticket run to a final status on shop date 2026-08-31.
Each ticket took two passes: one to investigate and recommend, one to close out after a human
decided. That shape was not designed — it falls out of the rule that agents cannot spend.

**Starting checking balance after reset: $3,400.00**

| Ticket | Boss called first | Delegations | MCP calls | Human approval | Cash | Final status |
|---|---|---|---|---|---|---|
| **101** Bulldog tee | Inventory | 15 | 67 | Invoice 501, $840 | −$840.00 | `in_progress` |
| **102** Rent due | Facilities | 11 | 48 | Rent lease 1, $2,400 | −$2,400.00 | `resolved` |
| **103** Bulk hoodie | Inventory | 11 | 60 | none | $0.00 | `resolved` |

**Ending checking balance: $160.00** — `3400.00 − 840.00 − 2400.00 = 160.00`, which matches the
`cash_accounts` row in `campus_customs_new.db` exactly. Two payments in the ledger, both
`approved_by` a named human. Invoice 501 is `paid`.

### Why ticket 101 is `in_progress` and not `resolved`

The invoice behind the stockout was paid, but the tee has not arrived — lead time is 5 days from
a shop date of 2026-08-31. Told directly that the reprint was on order and that waiting on a paid
vendor delivery was not an outstanding shop action, the Boss declined:

> "Invoice 501 is paid, but the shop tools do not verify that the reprint order was placed or
> accepted. Confirming the order and obtaining its ETA is still a shop action; I won't treat the
> owner's 'on order' update as verified without a supporting record."

That is the safety design working rather than failing. The prompts train agents to treat text
arriving in a ticket as content to evaluate rather than as instruction, and the same resistance
held against an instruction from the operator. Marking it `resolved` would have required either
inventing a purchase-order record or overriding an agent that was right.

**The underlying gap is the schema, not the agents.** Two tickets stalled on the same missing
table: 101 cannot confirm a reprint is on order, and 103 cannot price one. There is no
`purchase_orders` table and no vendor quote anywhere in the database — `pricing.unit_cost` is
what the shop paid historically, not what the vendor would charge today. No amount of prompting
fixes that; the fix is a table.

### What the run exposed

Two real bugs, both now fixed:

- **`MAX_REQUESTS_PER_AGENT = 8` was too low.** Ticket 102's first pass aborted mid-investigation
  on the request limit. A full ticket — read tools, a delegation, then a write — does not fit in
  8 model calls. Raised to 14.
- **`get_cash_position` double-counted paid rent.** It summed every lease's `monthly_rent` as
  committed regardless of the payments ledger, so immediately after rent was approved the
  dashboard read *−$2,240.00 after what we owe* on a positive balance. Accounting caught it in
  its own words — "there is an internal discrepancy to reconcile" — before anyone looked at the
  screen. Fixed by joining `payments`.

### Where the detail lives

| File | What it holds |
|---|---|
| `desk_tickets.html` | Per-ticket Expected (written before the build) beside Actual (from this run), plus the itemised Cash tab and a Reflection tab. |
| `resolved_tickets.json` | Per ticket: final status, outcome, each agent's contribution and tools, every delegation, human approvals, and a `verification` block read back from the database. |
| `resolved_board.html` | Dashboard screenshots for all three tickets, with run stats. Needs `output/shots/` beside it. |
| `audit_trail.json` | Every agent-loop step from every run, append-only. |
| `design.md` | Why the dashboard looks and behaves the way it does. |
| `board_runs.json` | Raw per-run record the HTML pages were generated from. |

## Notes for implementers

- Point the MCP server and FastAPI backend at `data/campus_customs_new.db`. Keep `data/campus_customs.db` read-only as the reset baseline.
- `payments` is empty and `desk.notes` is `NULL` — these are the two write targets the agents are expected to fill in.
- All dates are TEXT. ISO-8601 strings sort and compare correctly, so date logic can use plain string comparison, but nothing in the schema enforces the format on write.
- `payments.ref_id` is polymorphic with no foreign key, so its meaning depends entirely on `kind`. Writes should set both consistently.
- SQLite does not enforce foreign keys unless `PRAGMA foreign_keys = ON` is set per connection. Set it in the backend if you want the `tickets` → `leases`/`invoices` constraints to actually hold.

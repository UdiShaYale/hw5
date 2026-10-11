# Campus Customs MCP Server

## What it is for

This is the **single shop-tools layer** for the Campus Customs agentic team. The shop
is run by five agents (Boss, Inventory, Accounting, Facilities, Customer Service)
working a ticket queue, and this server is how all of them read and change shop
state. There is deliberately no second data path — nothing under `backend/` opens
SQLite directly. If a fact about the shop did not come back from a tool here, no
agent is allowed to assert it.

The FastAPI backend and React dashboard sit on top of this same server.

Built with [FastMCP](https://github.com/jlowin/fastmcp).

## Which database it uses

`../data/campus_customs_new.db` — the working copy.

`../data/campus_customs.db` is the untouched original and is **not** opened by this
server. It stays as the reset baseline.

Foreign keys are enabled per connection (`PRAGMA foreign_keys = ON`), so the
`tickets` → `leases` / `invoices` references are actually enforced on write.

## The tools

14 tools: 10 reads and 4 writes. Every tool returns exactly what is stored. When a
lookup finds nothing it returns `{"found": false}`, and when a write is refused it
returns `{"ok": false, "error": ...}` — never a plausible substitute value.

### Read tools

| Tool | Table(s) | What it is for |
|---|---|---|
| `get_shop_date()` | `desk` | The shop's simulated business date, plus desk notes. Every overdue / due-in-N-days judgement must be measured against this, not wall-clock time. |
| `list_tickets(status="open")` | `tickets` | The team's work queue. Pass `status="all"` for every ticket. |
| `check_inventory_stock(sku, size)` | `inventory` | On-hand count for one `(sku, size)`. Both args required — the table is keyed on the pair. |
| `list_sizes_for_sku(sku)` | `inventory` | The whole size run for a SKU, to see what else is available. |
| `get_sku_pricing(sku)` | `pricing` | `unit_cost` and `list_price`. Stored per SKU, not per size. |
| `get_lease_terms(lease_id)` | `leases` | The signed rent amount and next due date — the authority a rent notice is checked against. |
| `get_invoice(invoice_id)` | `invoices` + `vendors` | One invoice with vendor name and lead time attached, plus `days_overdue` already computed against the shop date. |
| `list_vendors(specialty="")` | `vendors` | Vendors and their `lead_days`, optionally filtered by specialty substring. |
| `get_cash_position()` | `cash_accounts` + `invoices` + `leases` + `desk` | Balances stacked against open invoices and lease rent, with `cash_after_commitments`. The affordability picture in one call. |
| `list_payments()` | `payments` | What has already been paid, so nothing is paid twice. |

### Write tools

| Tool | Table(s) | What it is for |
|---|---|---|
| `record_payment(kind, ref_id, amount, account, approved_by)` | `payments` + `cash_accounts` + `invoices` | Pays an invoice or rent: debits cash, logs the payment, closes a paid invoice. |
| `adjust_inventory_qty(sku, size, delta, reason)` | `inventory` | Moves stock for a real event — an order filled, a reprint received. A written `reason` is required. |
| `update_ticket_status(ticket_id, status, resolution_note)` | `tickets` | Moves a ticket to `open`/`in_progress`/`resolved`/`cancelled`/`needs_human` and **appends** the note without overwriting existing notes. |
| `append_desk_note(note)` | `desk` | Appends a dated line to the shared handover log. Never erases earlier notes. |

### What the write tools refuse

These are enforced in the server, so they hold no matter what an agent was
persuaded to try:

- `record_payment` refuses an empty `approved_by`, a non-positive amount, an amount
  that does not match the obligation on file, an unknown account or obligation, an
  invoice that is not `open`, a duplicate payment for the same `(kind, ref_id)`, and
  any payment that would overdraw the account.
- `adjust_inventory_qty` refuses a missing reason, a zero delta, an unstocked
  `(sku, size)`, and any change that would drive a count below zero.
- `update_ticket_status` refuses an unrecognised status and an empty note.
- `append_desk_note` refuses an empty note.

The agent side adds a second lock: `record_payment` is blocked client-side unless
the run was started with spending approved. See `backend/agents/shop_mcp.py`.

## Running it

Registered in the workspace `.mcp.json` as `campus-customs`.

```bash
# stdio (the usual MCP transport; this is how the agents connect)
python mcp_server.py

# HTTP, for local poking
python mcp_server.py --http      # http://127.0.0.1:8002/mcp
```

Requires `fastmcp`. The server exits with a clear error if the working database is
missing from `../data/`.

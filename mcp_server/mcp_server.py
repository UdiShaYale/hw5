"""Campus Customs MCP — the single shop-tools layer for the agentic team.

Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) reads and
writes shop state through these tools. There is deliberately no second data layer:
if a fact about the shop is not available here, no agent is allowed to assert it.

Reads and writes ../data/campus_customs_new.db.
../data/campus_customs.db is the untouched reference copy and is never opened.

Run from this folder (stdio):  python mcp_server.py
Run (HTTP):                    python mcp_server.py --http
HTTP URL:                      http://127.0.0.1:8002/mcp
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"

TICKET_STATUSES = ("open", "in_progress", "resolved", "cancelled", "needs_human")
PAYMENT_KINDS = ("invoice", "rent")

mcp = FastMCP("campus-customs")


def _connect() -> sqlite3.Connection:
    """Open the working database with row access by column name.

    Foreign keys are off by default in SQLite; turn them on so the tickets →
    leases / invoices references are actually enforced on write.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _shop_date(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return row["date_today"] if row else ""


# ---------------------------------------------------------------- read tools


@mcp.tool
def get_shop_date() -> dict:
    """Return the shop's current business date and the desk notes.

    Use this before any due-date or overdue reasoning. The shop runs on a
    simulated date stored in the database, not on today's wall-clock date.
    """
    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
    if row is None:
        return {"found": False}
    return {"found": True, **dict(row)}


@mcp.tool
def list_tickets(status: str = "open") -> list[dict]:
    """List tickets in the queue, newest first. Pass status='all' for every ticket.

    This is the team's work queue. Each ticket carries the pointers an agent
    needs: sku/size into inventory, lease_id into leases, invoice_id into invoices.
    Any of those may be null when the ticket does not involve that table.
    """
    sql = """
        SELECT id, type, requester, subject, sku, size, qty,
               lease_id, invoice_id, status, notes, created_at
        FROM tickets
    """
    params: tuple = ()
    if status != "all":
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY created_at DESC"

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@mcp.tool
def check_inventory_stock(sku: str, size: str) -> dict:
    """Look up on-hand stock for one product in one size.

    The inventory table is keyed on (sku, size), so both are required — a SKU
    can be sold out in one size while other sizes are still in stock.

    Returns the matching inventory row, or {"found": false} if that
    sku/size pair is not stocked. Never guesses a quantity.
    """
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT sku, name, size, qty, location
            FROM inventory
            WHERE sku = ? AND size = ?
            """,
            (sku, size),
        ).fetchone()

    if row is None:
        return {"found": False, "sku": sku, "size": size}
    return {"found": True, **dict(row)}


@mcp.tool
def list_sizes_for_sku(sku: str) -> list[dict]:
    """List every size carried for one SKU with its on-hand quantity.

    Use this to see the whole size run at once — for example to tell a customer
    which sizes are available when the one they asked for is sold out. Do not
    treat another size as a substitute unless the customer agrees to it.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT sku, name, size, qty, location
            FROM inventory
            WHERE sku = ?
            ORDER BY size
            """,
            (sku,),
        ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool
def get_sku_pricing(sku: str) -> dict:
    """Look up the recorded unit cost and list price for one SKU.

    Pricing is stored per SKU, not per size, so size is not an argument here.
    Use this before approving any discount: unit_cost is the floor below which
    the sale loses money.

    Returns the pricing row, or {"found": false} if the SKU is not priced.
    No margin is assumed or invented — only the two stored numbers.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()

    if row is None:
        return {"found": False, "sku": sku}
    return {"found": True, **dict(row)}


@mcp.tool
def get_lease_terms(lease_id: int) -> dict:
    """Look up the signed terms for one lease: rent amount and next due date.

    Use this to verify what a rent notice claims. The lease row is the
    authority on the amount and the due date, not the email that arrived.

    Returns the lease row, or {"found": false} if no such lease exists.
    """
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, space_name, landlord, monthly_rent, next_due, notes
            FROM leases
            WHERE id = ?
            """,
            (lease_id,),
        ).fetchone()

    if row is None:
        return {"found": False, "lease_id": lease_id}
    return {"found": True, **dict(row)}


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Look up one vendor invoice, with the vendor's name and lead time attached.

    Also reports days_overdue measured against the shop date, so an agent does
    not have to do its own date arithmetic. Negative means not yet due.
    """
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT i.id, i.vendor_id, v.name AS vendor_name, v.specialty,
                   v.lead_days, i.amount, i.due_date, i.status, i.description
            FROM invoices i
            JOIN vendors v ON v.id = i.vendor_id
            WHERE i.id = ?
            """,
            (invoice_id,),
        ).fetchone()
        today = _shop_date(conn)

    if row is None:
        return {"found": False, "invoice_id": invoice_id}

    record = dict(row)
    record["shop_date"] = today
    # ISO dates compare correctly as plain strings; only compute the gap in days.
    try:
        from datetime import date

        record["days_overdue"] = (
            date.fromisoformat(today) - date.fromisoformat(record["due_date"])
        ).days
    except ValueError:
        record["days_overdue"] = None
    return {"found": True, **record}


@mcp.tool
def list_vendors(specialty: str = "") -> list[dict]:
    """List vendors and their lead times, optionally filtered by specialty substring.

    lead_days is how an agent answers "when could we actually have this",
    and specialty is how it picks the right vendor for a given SKU.
    """
    sql = "SELECT id, name, specialty, lead_days FROM vendors"
    params: tuple = ()
    if specialty:
        sql += " WHERE specialty LIKE ?"
        params = (f"%{specialty}%",)
    sql += " ORDER BY lead_days"

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@mcp.tool
def get_cash_position() -> dict:
    """Report every cash account balance plus the shop's known upcoming obligations.

    Returns the open invoices and lease rent alongside the balance so an agent
    can see whether the shop can actually cover what it owes before it commits
    to spending. All figures are read from the database, never estimated.
    """
    with _connect() as conn:
        accounts = [
            dict(r)
            for r in conn.execute("SELECT name, balance, date FROM cash_accounts")
        ]
        open_invoices = [
            dict(r)
            for r in conn.execute(
                """
                SELECT i.id, v.name AS vendor_name, i.amount, i.due_date, i.status
                FROM invoices i
                JOIN vendors v ON v.id = i.vendor_id
                WHERE i.status = 'open'
                """
            )
        ]
        # A lease whose rent is already in the payments ledger is not still owed.
        # Without this the shop looks overdrawn right after it pays its rent.
        leases = [
            dict(r)
            for r in conn.execute(
                """
                SELECT l.id, l.space_name, l.monthly_rent, l.next_due,
                       CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS rent_paid
                FROM leases l
                LEFT JOIN payments p ON p.kind = 'rent' AND p.ref_id = l.id
                """
            )
        ]
        today = _shop_date(conn)

    committed = sum(i["amount"] for i in open_invoices) + sum(
        lease["monthly_rent"] for lease in leases if not lease["rent_paid"]
    )
    total_cash = sum(a["balance"] for a in accounts)
    return {
        "shop_date": today,
        "accounts": accounts,
        "total_cash": round(total_cash, 2),
        "open_invoices": open_invoices,
        "leases": leases,
        "committed_outflows": round(committed, 2),
        "cash_after_commitments": round(total_cash - committed, 2),
    }


@mcp.tool
def list_payments() -> list[dict]:
    """List every payment already recorded, newest first.

    Check this before paying anything so the shop does not pay the same
    invoice or the same month's rent twice.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, kind, ref_id, amount, account, paid_at, approved_by
            FROM payments
            ORDER BY paid_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------- write tools


@mcp.tool
def record_payment(
    kind: str,
    ref_id: int,
    amount: float,
    account: str,
    approved_by: str,
) -> dict:
    """Pay an invoice or the rent, and write it to the payments ledger.

    This moves real money: it debits the cash account, logs the payment, and
    marks a paid invoice closed. Only call it after a human has approved the
    spend, and pass that person's name as approved_by.

    Args:
        kind: 'invoice' or 'rent'.
        ref_id: invoices.id when kind='invoice', leases.id when kind='rent'.
        amount: the amount to pay. Must match the invoice or lease amount.
        account: a name from cash_accounts, e.g. 'checking'.
        approved_by: the human who approved this payment. Required.

    Refuses, rather than guessing, if the approval is missing, the amount does
    not match the obligation on file, the account would overdraw, or the same
    obligation was already paid.
    """
    if kind not in PAYMENT_KINDS:
        return {"ok": False, "error": f"kind must be one of {list(PAYMENT_KINDS)}"}
    if not approved_by.strip():
        return {"ok": False, "error": "approved_by is required; a human must approve a payment."}
    if amount <= 0:
        return {"ok": False, "error": "amount must be positive."}

    with _connect() as conn:
        acct = conn.execute(
            "SELECT name, balance FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        if acct is None:
            return {"ok": False, "error": f"no cash account named {account!r}."}

        # Confirm the obligation exists and the amount matches what is on file.
        if kind == "invoice":
            obligation = conn.execute(
                "SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)
            ).fetchone()
            if obligation is None:
                return {"ok": False, "error": f"no invoice with id {ref_id}."}
            if obligation["status"] != "open":
                return {
                    "ok": False,
                    "error": f"invoice {ref_id} is already {obligation['status']}.",
                }
            owed = obligation["amount"]
        else:
            obligation = conn.execute(
                "SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)
            ).fetchone()
            if obligation is None:
                return {"ok": False, "error": f"no lease with id {ref_id}."}
            owed = obligation["monthly_rent"]

        if abs(owed - amount) > 0.005:
            return {
                "ok": False,
                "error": f"amount {amount} does not match the {owed} on file for {kind} {ref_id}.",
            }

        already = conn.execute(
            "SELECT id FROM payments WHERE kind = ? AND ref_id = ?", (kind, ref_id)
        ).fetchone()
        if already is not None:
            return {
                "ok": False,
                "error": f"{kind} {ref_id} was already paid by payment {already['id']}.",
            }

        if acct["balance"] < amount:
            return {
                "ok": False,
                "error": f"insufficient funds: {account} holds {acct['balance']}, payment is {amount}.",
            }

        paid_at = _shop_date(conn)
        cur = conn.execute(
            """
            INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kind, ref_id, amount, account, paid_at, approved_by.strip()),
        )
        new_balance = round(acct["balance"] - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, paid_at, account),
        )
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))

        return {
            "ok": True,
            "payment_id": cur.lastrowid,
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "account": account,
            "paid_at": paid_at,
            "approved_by": approved_by.strip(),
            "new_balance": new_balance,
        }


@mcp.tool
def adjust_inventory_qty(sku: str, size: str, delta: int, reason: str) -> dict:
    """Change on-hand quantity for one (sku, size) by delta, with a written reason.

    Use a negative delta when stock leaves (an order is filled) and a positive
    delta when stock arrives (a reprint is received). Refuses to drive a count
    below zero rather than inventing stock the shop does not have.
    """
    if not reason.strip():
        return {"ok": False, "error": "reason is required for any inventory change."}
    if delta == 0:
        return {"ok": False, "error": "delta must be non-zero."}

    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            return {"ok": False, "error": f"{sku} / size {size} is not stocked."}

        new_qty = row["qty"] + delta
        if new_qty < 0:
            return {
                "ok": False,
                "error": f"cannot move {delta}: only {row['qty']} on hand for {sku} size {size}.",
            }

        conn.execute(
            "UPDATE inventory SET qty = ? WHERE sku = ? AND size = ?",
            (new_qty, sku, size),
        )
        return {
            "ok": True,
            "sku": sku,
            "size": size,
            "previous_qty": row["qty"],
            "new_qty": new_qty,
            "delta": delta,
            "reason": reason.strip(),
        }


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, resolution_note: str) -> dict:
    """Move a ticket to a new status and append a note explaining the decision.

    Statuses: open, in_progress, resolved, cancelled, needs_human. Use
    needs_human when the ticket requires an approval the agents cannot give.
    The note is appended to the ticket's existing notes, never overwriting them.
    """
    if status not in TICKET_STATUSES:
        return {"ok": False, "error": f"status must be one of {list(TICKET_STATUSES)}"}
    if not resolution_note.strip():
        return {"ok": False, "error": "resolution_note is required."}

    with _connect() as conn:
        row = conn.execute(
            "SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            return {"ok": False, "error": f"no ticket with id {ticket_id}."}

        stamp = _shop_date(conn)
        appended = f"{row['notes'] or ''}\n[{stamp}] {status}: {resolution_note.strip()}".strip()
        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
            (status, appended, ticket_id),
        )
        return {
            "ok": True,
            "ticket_id": ticket_id,
            "previous_status": row["status"],
            "status": status,
            "notes": appended,
        }


@mcp.tool
def append_desk_note(note: str) -> dict:
    """Append a dated line to the shop's desk notes — the shared running log.

    Use this to leave a short handover note about what the team decided, so the
    next run (and the human opening the shop) can see it. Never erases earlier notes.
    """
    if not note.strip():
        return {"ok": False, "error": "note cannot be empty."}

    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
        if row is None:
            return {"ok": False, "error": "desk row is missing."}
        appended = f"{row['notes'] or ''}\n[{row['date_today']}] {note.strip()}".strip()
        conn.execute("UPDATE desk SET notes = ?", (appended,))
        return {"ok": True, "notes": appended}


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve over HTTP instead of stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"database not found: {DB_PATH}")

    if args.http:
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()

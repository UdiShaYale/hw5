# Campus Customs — dashboard

React + Vite + TypeScript. Talks to the FastAPI backend at `http://localhost:8000`.

## Run it

Two terminals.

```bash
# 1 — backend, from hw 5/backend
uvicorn main:app --reload --port 8000

# 2 — dashboard, from hw 5/frontend
npm run dev          # http://localhost:5173
```

The backend allows the Vite origin (`http://localhost:5173`) via CORS, so the
browser is permitted to call the routes.

To point at a different backend, set `VITE_API_BASE` in a `.env` here.

## What it does

- Lists the three tickets, with status and the SKU / invoice / lease pointers.
- Pick one and press **Run the team** — the run starts in the background and the
  page follows it live.
- Shows each agent working: who is active, what tool they just called, and who
  delegated to whom.
- Writes to the database are flagged amber; blocked tool calls are flagged red.
- After the run: the Boss's decision, then a per-agent summary of what each one did.
- When a ticket lands on **Needs you**, an approval panel appears. Approving is
  the only action in the app that moves money, and it requires a name.
- The checking balance sits in the header and flashes when an approval drops it.
- **Reset shop data** restores the database to its original values. The audit
  trail is left intact.

Design rationale is in `../output/design.md`.

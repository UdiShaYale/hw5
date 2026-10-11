# Dashboard design — Campus Customs agent desk

React + Vite + TypeScript, talking to the FastAPI backend at `http://localhost:8000`.

The brief was "make it look good," but the real test is narrower: a person watches
five agents argue about money and then has to decide whether to pay. Every choice
below is in service of that moment.

---

## The governing idea

**The agents are advisors. The human is the only one who can spend.**

That is the actual rule in the backend — `/tickets/{id}/run` always passes
`allow_spending=False`, and cash only moves on `/approve`. A dashboard that
rendered agent output and payment buttons in the same visual language would
quietly undermine it: everything would look equally like "the system doing
things." So the interface splits along that line and keeps the split visible.

Everything the agents produce is **blue**. The one control that moves money is
**amber**, in its own bordered panel, with a name field that must be filled
before the button enables. The colour change is not decoration — it marks the
boundary between a recommendation and a decision.

---

## Layout

A two-column desk, not a dashboard grid.

```
┌──────────────────────────────────────────────────────────────┐
│  CC  Campus Customs              Checking $3,400.00   [Reset]│  ← sticky
│      Agent desk · shop date        $160.00 after what we owe │
├──────────────────┬───────────────────────────────────────────┤
│  TICKET QUEUE    │  #101 — Bulldog tee      [Open] [Run team]│
│                  ├───────────────────────────────────────────┤
│  ┌────────────┐  │  ┌────┐┌────┐┌────┐┌────┐┌────┐           │
│  │ #101  ●    │  │  │Boss││Inv ││Acct││Fac ││ CS │  agents   │
│  └────────────┘  │  └────┘└────┘└────┘└────┘└────┘           │
│  ┌────────────┐  │                                           │
│  │ #102       │  │  LIVE TRANSCRIPT                     ⟳    │
│  └────────────┘  │  ┌─────────────────────────────────────┐  │
│  ┌────────────┐  │  │ SB  Shop Boss          0.4s         │  │
│  │ #103       │  │  │     list_tickets status=open        │  │
│  └────────────┘  │  │ IN  Inventory → Accounting          │  │
│                  │  │ AC  Accounting    WRITE   12.1s     │  │
│                  │  └─────────────────────────────────────┘  │
│                  │                                           │
│                  │  THE BOSS'S CALL        (dark panel)      │
│                  │  WHAT EACH AGENT DID    (summary cards)   │
│                  │  WAITING ON YOU         (amber, approve)  │
└──────────────────┴───────────────────────────────────────────┘
```

**Why a narrow fixed rail for tickets.** There are exactly three, and they never
grow. A rail keeps all three permanently visible so you can switch context
without losing your place, and it lets the main column stay wide enough for the
transcript to be readable rather than a column of wrapped fragments.

**Why the main column is vertical and ordered.** It reads as a story in the order
the work happens: *who is working* → *what they are saying* → *what was decided*
→ *what you have to do about it*. The approval panel is last on purpose. You
reach it by scrolling past the evidence.

**Why the balance is in a sticky header.** It is the number that changes as a
consequence of your click, and the only piece of state that matters on every
screen. It stays pinned so the cause and the effect are never separated by a
scroll.

---

## How the agents read differently

Five agents in one feed becomes mush unless each is distinguishable at a glance.
Three layers do that work:

**1. Colour, varied by depth rather than hue.** Every agent gets a different
blue — Boss `#1d4ed8`, Inventory `#2563eb`, Accounting `#0ea5e9`, Facilities
`#3b82f6`, Customer Service `#60a5fa`. The colours come from the backend's
`/agents` roster, so the Python and the UI cannot drift apart. Staying inside one
hue family means the five read as *one team* rather than five unrelated services,
while still being individually identifiable. It also leaves amber and red free to
mean something — money and refusal — instead of just being the next agent's colour.

**2. The Boss is built differently, not just coloured differently.** The Boss chip
has a dark navy fill while the specialists are on white. It is the only agent that
owns the queue and writes the final decision, and hierarchy should be legible
without reading the labels.

**3. Event *type* has its own visual grammar**, so you can tell talking from doing
from handing-off without reading a word:

| What happened | How it looks |
|---|---|
| An agent said something | Plain white card, the agent's own words |
| An agent called a read tool | Faint blue tint, tool name in mono |
| An agent **wrote to the database** | Amber card + `WRITE` badge |
| A tool call was **blocked by a guard rail** | Red card + `BLOCKED` badge |
| One agent delegated to another | Dashed border, `Inventory → Accounting` |
| Run started / finished | Dark navy milestone bar |

The amber-write rule matters more than it looks. In a system where agents can
change shop state, "this step changed something" is the single most important
thing a supervising human needs to spot, and it should never require reading the
tool name to notice. Blocked calls are red for the same reason inverted: when a
guard rail fires, that is a safety event, and it should be as loud as a write.

**Depth badges** (`d1`, `d2`) appear on delegated work. The team is fully
connected — Accounting really can ask Inventory something mid-run — and the badge
is what makes that visible instead of mysterious.

---

## Tickets

Each ticket is a single card, and the **whole card is the button**. No separate
"select" affordance, because there is only one thing you can do to a ticket card.

Cards carry the structural pointers as monospace chips — `CC-TEE-WHITE · S`,
`qty 1`, `invoice 501`. These are exactly the foreign keys the agents will follow,
so the card previews the shape of the work rather than just naming it.

The **left border is a status stripe**: blue when idle, amber while agents are
working, green when closed. It is a second, redundant channel alongside the pill,
so status survives peripheral vision.

**Status vocabulary is deliberately plain.** `needs_human` renders as **"Needs
you."** Not "Pending approval," not "Blocked." The whole design rests on the human
understanding they are the gate, and the status label is the cheapest place to say
so. `needs_human` and `running` are the only statuses that get an animated dot —
the two states that are asking for attention.

One honest note: the brief said "mark a ticket resolved when the run finishes."
The dashboard shows whichever status the agents actually set, which in practice is
usually `needs_human`, not `resolved`. Painting a ticket "Resolved" while an
unpaid invoice is still outstanding would be a comfortable lie, and would defeat
the approval flow sitting directly beneath it.

---

## Cash

The balance lives in the header as a large tabular-numeral figure, with
`$160.00 after what we owe` beneath it in small type. One number is what you
*have*; the other is what you have *left* — and for this shop those differ by a
factor of twenty. Showing only the balance would make the shop look comfortable
when it is not.

**When an approval goes through, the balance reacts.** The tile flashes amber and
a delta (`-$840.00`) floats up and fades. This is the one piece of motion in the
product that is not purely functional, and it earns its place: approving a payment
is the only irreversible thing a user can do here, and it should *feel* like
something happened rather than silently re-rendering. The flash is tied to an
actual decrease, so it can never fire on a refresh.

The approval panel only lists obligations that are genuinely open — it reads
`/cash`, so a paid invoice simply stops appearing. Buttons disable themselves when
the balance would not cover the amount, with the reason in the tooltip rather than
a modal. The backend would refuse anyway; the UI just refuses earlier and more
kindly.

---

## The creative choices that make it feel like a desk

**It is a desk, not a dashboard.** No KPI tiles, no sparklines, no donut of ticket
statuses. Three tickets do not need analytics. The metaphor is a shopkeeper's desk
with a stack of work on the left and the current job in front of you — which is
what the `desk` table in the database is already called.

**The transcript auto-follows, but yields.** It scrolls to the newest event while
running, and stops the moment you scroll up to read something, resuming only when
you return to the bottom. Watching agents work is genuinely interesting, and an
interface that yanks the viewport away mid-sentence makes that impossible.

**Agent chips show live verbs.** While running, the active agent's card reads
`called get_cash_position…` or `asked Accounting…` with a sweeping underline. You
can follow the work from the strip alone, without parsing the feed. Idle agents
sit at 55% opacity, so "who has not been involved yet" is readable at a glance —
which turned out to be genuinely diagnostic: on ticket 101, Facilities correctly
stays grey the whole run.

**Token cost is shown, not hidden.** The decision panel footer carries the model,
delegation count, tool calls and token in/out. Agent teams are expensive and the
cost is a design constraint, not an embarrassment. Putting it on screen makes the
tradeoff of "run the team again" a visible one.

**Summary cards answer a different question than the feed.** The feed is
chronological and interleaved; the summary is per-agent, showing each agent's
closing statement and the distinct tools it used. After an 80-second run with 79
events, "what did Accounting conclude" should not require scrolling.

**Errors are specific and actionable.** If the backend is down, the message is
*"Cannot reach the backend at http://localhost:8000. Start it with: uvicorn
main:app --reload --port 8000"* — the fix, not the symptom. A refused payment
surfaces the backend's own reason ("amount 999.0 does not match the 840.0 on
file") rather than a generic failure.

---

## Accessibility and restraint

- Status is never carried by colour alone — pill text, border stripe and a dot all
  say the same thing.
- The feed is `role="log"` with `aria-live="polite"`, so a screen reader hears
  agent activity without the page being re-announced wholesale.
- Ticket cards are real `<button>`s with `aria-pressed`; the strip is keyboard
  reachable; focus rings are a visible 3px blue.
- `prefers-reduced-motion` kills every animation — the pulse, the sweep, the cash
  flash — because all of them are redundant with a static signal.
- Tabular numerals everywhere money or counts appear, so digits do not jitter as
  values update during polling.

---

## What I would change with more time

Polling every 1.2s is the weak point. Server-sent events would be the right
transport — the backend already emits discrete steps into a queue, so the plumbing
largely exists. Polling was chosen because it works against the routes as
specified and fails gracefully if a request is dropped; a dropped SSE connection
needs reconnection logic to avoid a feed that silently stops.

Beyond that: the approval panel lists every open obligation rather than only the
one the agents actually recommended for this ticket, because the recommendation
lives in prose rather than in a structured field. Having the Boss emit a typed
`proposed_payment` object would let the UI show exactly what was recommended, and
flag the case where a human approves something the agents did *not* propose.

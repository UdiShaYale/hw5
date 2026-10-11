"""Fill the Reflection tab of output/desk_tickets.html.

Answers the five reflection questions, citing the ticket tabs and the cash tab
on the same page as evidence.

    python build_reflection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "output"
PAGE = OUT / "desk_tickets.html"

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PANEL = """<div class="cash-wrap">
    <h2 style="margin:0 0 .3rem">Reflection</h2>
    <p class="sub" style="margin:0 0 1.4rem">
      Five questions about the board, answered against the evidence on the
      <strong>Ticket&nbsp;101 / 102 / 103</strong> tabs and the <strong>Cash</strong> tab.
      Every claim below points at something you can go and check.
    </p>

    <!-- ========== 1. performance per ticket ========== -->
    <h3 class="cash-h3">1 &mdash; How the team performed on each ticket</h3>

    <div class="card grade">
      <h3><span class="num">A</span> Ticket 101 &mdash; Bulldog tee <span class="mark strong">strong, expensive</span></h3>
      <p><strong>What it got right.</strong> It found the real blocker rather than the obvious one.
      Size S was at <code>qty 0</code>, and the team followed the ticket's <code>invoice_id</code>
      to invoice 501 &mdash; the $840 rush reprint of this exact SKU and size, three days overdue.
      That link is the whole ticket, and it was never going to be found by reading the subject line.
      <span class="ev">Evidence: Ticket&nbsp;101 tab &rarr; Actual &sect;3, where
      <code>check_inventory_stock</code> and <code>get_invoice</code> both appear.</span></p>
      <p><strong>It refused to invent the two things it did not have.</strong> It never promised a
      delivery date, because <code>lead_days</code> is a vendor lead time and no order confirmation
      exists. And it would not mark the ticket <code>resolved</code> after the invoice was paid,
      because the customer still has no tee.
      <span class="ev">Evidence: Ticket&nbsp;101 tab &rarr; Actual &sect;7, the one
      <em>differed</em> chip in that section.</span></p>
      <p><strong>What it cost.</strong> Three passes, 15 delegations, 104 tool calls &mdash; the
      most expensive ticket on the board by a wide margin, for an outcome that is "paid the invoice,
      told the customer the truth." Much of that was re-reading state each pass rather than new work.
      <span class="ev">Evidence: Ticket&nbsp;101 tab &rarr; Actual &sect;2 and &sect;3.</span></p>
      <p class="verdict-line">A correct and well-reasoned outcome at roughly double the cost it
      needed. The judgement was better than the efficiency.</p>
    </div>

    <div class="card grade">
      <h3><span class="num">B</span> Ticket 102 &mdash; Rent due <span class="mark mixed">right answer, messiest process</span></h3>
      <p><strong>What it got right.</strong> It treated an inbound email as a claim rather than a
      bill. It compared the amount, the date and the sender against lease 1, confirmed
      <code>next_due 2026-09-02</code> was genuinely two days from the shop date, and flagged that
      <em>the notice itself named no amount</em> &mdash; the $2,400 came only from the lease row.
      That is the single most security-relevant thing any agent did all day.
      <span class="ev">Evidence: Ticket&nbsp;102 tab &rarr; Actual &sect;7, four
      <em>as predicted</em> chips.</span></p>
      <p><strong>It caught a bug in its own tooling.</strong> Accounting noticed that
      <code>get_cash_position</code> still reported a $2,400 lease commitment after payment&nbsp;#2
      was recorded, and wrote it into the ticket notes as an "internal accounting caveat" rather than
      either ignoring it or treating the shop as overdrawn. It was right, and the bug is now fixed.
      <span class="ev">Evidence: Cash tab &rarr; the ledger shows payment&nbsp;#2; the caveat is in
      the Ticket&nbsp;102 tab &rarr; Actual &sect;4.</span></p>
      <p><strong>What went wrong.</strong> Pass 1 <strong>crashed</strong> partway through on the
      per-agent request limit, and Accounting alone called <code>update_ticket_status</code>
      <strong>four times</strong> on one ticket. The answer survived the mess; the process did not
      deserve to.
      <span class="ev">Evidence: Ticket&nbsp;102 tab &rarr; Actual &sect;2, pass&nbsp;1 row.</span></p>
      <p class="verdict-line">The best reasoning on the board wrapped in the worst execution.
      Both of those are worth taking seriously, and neither cancels the other.</p>
    </div>

    <div class="card grade">
      <h3><span class="num">C</span> Ticket 103 &mdash; Bulk hoodie discount <span class="mark strong">strongest discipline</span></h3>
      <p><strong>What it got right.</strong> It filtered on <code>(sku,&nbsp;size)</code> and found
      8 against an order of 20 &mdash; a 12-unit shortfall that disappears entirely if you sum the
      SKU across sizes (4+8+14+6 = 32). No agent made that mistake.
      <span class="ev">Evidence: Ticket&nbsp;103 tab &rarr; Actual &sect;3,
      <code>check_inventory_stock</code> and <code>list_sizes_for_sku</code> both called.</span></p>
      <p><strong>The best single call of the day.</strong> It refused to treat
      <code>pricing.unit_cost</code> ($22) as a quote for reprinting 12 more hoodies. It is the
      historic cost, not a price Bulldog Print Co has offered, and using it would have produced a
      confident, fully-sourced, completely fictional margin. It quoted the $36/unit headroom as a
      <em>bound</em> and declined to certify the deal.
      <span class="ev">Evidence: Ticket&nbsp;103 tab &rarr; Actual &sect;7, and the Cash tab row for
      #103 &mdash; $0.00 moved.</span></p>
      <p><strong>Where it is arguable.</strong> It chose <code>resolved</code> over
      <code>cancelled</code>, reasoning the request "is not established as impossible to fulfill."
      Defensible, and it explained itself &mdash; but the club got no hoodies and no price, so a
      human might reasonably have wanted this left open.</p>
      <p class="verdict-line">Cheapest ticket on the board and the one with the firmest grip on
      what it did and did not know.</p>
    </div>

    <div class="card warn">
      <h3><span class="num">!</span> One defect runs through all three</h3>
      <p><strong>Nobody owns ticket status.</strong> On ticket 101 four different agents called
      <code>update_ticket_status</code> seven times between them; on 102 it happened nine times.
      The Customer Service prompt says CS closes tickets out &mdash; but every agent can reach every
      tool, and prompts are guidance, not permissions. The last writer wins, which means the final
      status of a ticket is partly a race.
      <span class="ev">Evidence: Ticket&nbsp;101 and 102 tabs &rarr; Actual &sect;4, write counts
      per agent.</span></p>
      <p>Nothing went wrong here because every agent happened to agree. That is luck, not design.
      The fix is per-agent tool permissions at the MCP boundary, which this build does not have.</p>
    </div>

    <!-- ========== 2. expected vs actual ========== -->
    <h3 class="cash-h3">2 &mdash; Actual against the plan written beforehand</h3>

    <div class="card">
      <p>The Expected sections on each ticket tab were written from the schema <em>before</em> any
      agent code existed. Across all three tickets: <strong>14 predictions held, 2 missed.</strong></p>
      <table>
        <thead><tr><th>Ticket</th><th>Predicted first call</th><th>Actual</th><th></th></tr></thead>
        <tbody>
          <tr><td>101</td><td>Inventory</td><td>Inventory</td><td><span class="verdict-chip hit">as predicted</span></td></tr>
          <tr><td>102</td><td>Facilities</td><td>Facilities</td><td><span class="verdict-chip hit">as predicted</span></td></tr>
          <tr><td>103</td><td>Accounting</td><td><strong>Inventory</strong></td><td><span class="verdict-chip miss">differed</span></td></tr>
        </tbody>
      </table>
      <p><strong>101 and 102 went exactly to plan</strong>, including the two cross-agent hops that
      were called out in advance as the real test of whether the team was genuinely connected or
      just a star around the Boss: Inventory&nbsp;&rarr;&nbsp;Accounting fired on 101, and
      Facilities&nbsp;&rarr;&nbsp;Accounting on 102. Neither was routed by the Boss.
      <span class="ev">Evidence: Actual &sect;2 on both tabs.</span></p>
      <p><strong>103 is the one miss, and it missed in the shop's favour.</strong> The prediction was
      that the Boss would be pulled by the ticket's <code>price_override</code> label and call
      Accounting first; the prediction also argued, in the same breath, that Inventory was the
      correct opening move because there is no discount to approve on a quantity you cannot supply.
      The Boss called <strong>Inventory first</strong>. It read what the ticket needed rather than
      what it was labelled &mdash; the better behaviour, and the one not expected of it.</p>
      <p><strong>The one outcome the plan got wrong in the other direction</strong> was predicting
      101 would reach a clean stopping point. It did not: it sits at <code>in_progress</code>,
      because the reprint is paid for but has not arrived and no tool can confirm an order was even
      placed. The plan assumed paying the invoice ended the ticket. It does not.
      <span class="ev">Evidence: Cash tab &rarr; #101 row, &minus;$840.00 with the tee still at
      <code>qty 0</code>.</span></p>
      <p>Three traps were named in advance and none were hit: no agent summed inventory across
      sizes, none promised a delivery date, and none treated <code>unit_cost</code> as a reprint
      quote.</p>
    </div>

    <!-- ========== 3. one agent instead ========== -->
    <h3 class="cash-h3">3 &mdash; What would have been simpler as one agent with tools</h3>

    <div class="card">
      <p class="lead"><strong>Honestly: all three tickets.</strong> A single agent holding all 14
      MCP tools would have produced the same three outcomes, faster and for a fraction of the cost.</p>
      <p>The evidence is on the tabs. Across the board the team spent <strong>232 tool calls and 37
      delegations</strong> over 7 runs. Look at what the delegations actually carried &mdash;
      Inventory asking Accounting "can we afford this", Accounting asking Inventory "how many can we
      supply", Customer Service asking both before drafting. Those are not decisions that needed
      another mind. They are <em>tool calls wearing a costume</em>: a single agent answers each of
      them by calling <code>get_cash_position</code> or <code>check_inventory_stock</code> itself,
      in one step, with no prompt re-sent and no reply to parse.
      <span class="ev">Evidence: Actual &sect;2 on each ticket tab &mdash; read the questions, not
      the counts.</span></p>
      <p>The cost of the split is concrete and visible: every delegation re-sends a full system
      prompt and re-reads shop state, which is why the same handful of facts were fetched again and
      again. Ticket 101 called <code>get_shop_date</code> and <code>list_tickets</code> repeatedly
      across four agents who could not see each other's context.
      <span class="ev">Evidence: Ticket&nbsp;101 tab &rarr; Actual &sect;3, the per-agent call
      counts on shared tools.</span></p>
      <p><strong>What the team structure did buy</strong>, to be fair to it:</p>
      <ul>
        <li><strong>Legible separation of duty.</strong> Facilities verifies the lease; Accounting
        decides affordability; neither can pay. That reads clearly in the transcript and in the
        Cash tab ledger, and it is a real governance property.</li>
        <li><strong>An audit trail organised by role,</strong> which is why the Actual sections on
        these tabs could be written at all.</li>
        <li><strong>Narrower prompts,</strong> so each agent's rules are short enough to actually
        be followed &mdash; the discipline on ticket 103 plausibly comes from Accounting's prompt
        being about nothing but margin.</li>
      </ul>
      <p>But note what the separation is <em>not</em> doing: it is not what stops the shop
      overspending. That is enforced in the MCP server &mdash; <code>record_payment</code> refuses
      an empty <code>approved_by</code>, a mismatched amount, a duplicate or an overdraft &mdash;
      and in the backend, which disables spending on every agent run. A single agent hitting the
      same tools would be under exactly the same constraints.
      <span class="ev">Evidence: Cash tab &rarr; both ledger rows carry a human approver.</span></p>
      <p class="verdict-line">For a three-ticket board, one agent with these tools is the simpler
      and better engineering choice. The team earns its keep on <em>auditability and role clarity</em>,
      not on answer quality &mdash; and that is a trade worth making deliberately rather than by
      default.</p>
    </div>

    <!-- ========== 4. solvable ========== -->
    <h3 class="cash-h3">4 &mdash; Three new problems this team could already solve</h3>

    <div class="card">
      <h3><span class="num">1</span> "Which bill do we pay first this month?"</h3>
      <p>The shop will hit this every month, and it is the exact shape of the squeeze on the Cash
      tab: $3,240 of obligations against $3,400 of cash, leaving $160. Accounting already reads
      <code>get_cash_position</code>, <code>list_payments</code>, <code>get_invoice</code> and
      <code>get_lease_terms</code>, already computes <code>days_overdue</code> against the shop
      date, and already produced a reasoned payment order on this board.
      <span class="ev">Evidence: Cash tab &rarr; the per-ticket table is a worked example of this
      exact problem.</span> <strong>No new tools needed.</strong></p>
    </div>
    <div class="card">
      <h3><span class="num">2</span> A weekly stockout and reorder sweep</h3>
      <p>Nobody has noticed that <code>CC-MUG-CREST</code> is sitting at <code>qty 0</code> &mdash;
      it is in the database right now and no ticket mentions it. Inventory can already walk every
      SKU with <code>list_sizes_for_sku</code>, match a vendor by specialty with
      <code>list_vendors</code>, and turn <code>lead_days</code> into a real date via
      <code>get_shop_date</code>. Point the Boss at "find everything at zero" instead of a ticket id
      and this works today.
      <span class="ev">Evidence: Ticket&nbsp;103 tab &rarr; Actual &sect;3 is this query, run once
      by hand.</span> <strong>No new tools needed.</strong></p>
    </div>
    <div class="card">
      <h3><span class="num">3</span> Catching a duplicate or inflated vendor invoice</h3>
      <p>A vendor re-sends an invoice, or sends one for an amount nobody agreed. The team already
      checks <code>list_payments</code> before recommending a payment, and the MCP layer refuses a
      second payment against the same <code>(kind,&nbsp;ref_id)</code> and any amount that does not
      match the row on file. Accounting also already compares a claim against the record rather than
      accepting it &mdash; it did precisely that on ticket 102 with the rent notice.
      <span class="ev">Evidence: Ticket&nbsp;102 tab &rarr; Actual &sect;1; Cash tab &rarr; exactly
      two ledger rows, no duplicates.</span> <strong>No new tools needed.</strong></p>
    </div>

    <!-- ========== 5. not solvable ========== -->
    <h3 class="cash-h3">5 &mdash; Three it could not solve, and what each would take</h3>

    <div class="card gap">
      <h3><span class="num">1</span> "Where is the reprint, and when does it land?"</h3>
      <p><strong>Why it fails now.</strong> This is not hypothetical &mdash; it is the reason ticket
      101 is still <code>in_progress</code>. Invoice 501 is paid, but nothing in the database records
      that an order was placed, accepted, or given an ETA. The Boss said so itself and refused to
      close the ticket on an unverifiable claim.
      <span class="ev">Evidence: Ticket&nbsp;101 tab &rarr; Actual &sect;6.</span></p>
      <p><strong>What it would take.</strong> A <code>purchase_orders</code> table
      (<code>id</code>, <code>vendor_id</code>, <code>sku</code>, <code>size</code>,
      <code>qty</code>, <code>ordered_at</code>, <code>promised_date</code>, <code>status</code>,
      <code>invoice_id</code>) with MCP tools <code>place_purchase_order</code>,
      <code>get_purchase_order</code>, <code>list_open_orders</code> and
      <code>receive_delivery</code> &mdash; the last being what finally lets
      <code>adjust_inventory_qty</code> fire honestly on arrival. Plus a <strong>Purchasing
      agent</strong> owning the vendor relationship, so placing and chasing orders is somebody's job
      rather than a gap between Inventory and Accounting.</p>
    </div>

    <div class="card gap">
      <h3><span class="num">2</span> "What would 12 more hoodies actually cost us?"</h3>
      <p><strong>Why it fails now.</strong> The other half of ticket 103. There is no quote anywhere
      in the schema. <code>pricing.unit_cost</code> is what the shop paid historically, not what the
      vendor would charge today for a rush job of 12, and the team correctly refused to pretend
      otherwise &mdash; which is why it could not say whether any discount was profitable.
      <span class="ev">Evidence: Ticket&nbsp;103 tab &rarr; Actual &sect;7; Cash tab &rarr; #103,
      $0.00 moved.</span></p>
      <p><strong>What it would take.</strong> A <code>vendor_quotes</code> table
      (<code>vendor_id</code>, <code>sku</code>, <code>qty</code>, <code>unit_price</code>,
      <code>valid_until</code>, <code>lead_days</code>) and a <code>request_quote</code> /
      <code>get_quotes</code> tool pair. The honest version also needs an <strong>outbound channel
      &mdash; an email or vendor-portal tool</strong> &mdash; because a quote is a conversation with
      a human at Bulldog Print Co, not a database read. That makes it the first capability here that
      reaches outside the shop's own records, and it needs its own guard rails: agents drafting
      outbound messages should not be able to send them unreviewed.</p>
    </div>

    <div class="card gap">
      <h3><span class="num">3</span> "Is this rent notice actually from our landlord?"</h3>
      <p><strong>Why it fails now.</strong> On ticket 102 Facilities verified the amount, the date
      and the <em>name</em> against lease 1 &mdash; genuinely good work. But it cannot verify the
      <em>sender</em>. The notice is a row of text in the database; there are no headers, no sending
      address, no payee bank details to check. Change the notice to name a new account and the lease
      comparison still passes on amount, date and landlord name. This is the most common way small
      businesses actually lose money, and the current tooling cannot see it.
      <span class="ev">Evidence: Ticket&nbsp;102 tab &rarr; Actual &sect;1 &mdash; the three things
      it compared, and the fourth it could not.</span></p>
      <p><strong>What it would take.</strong> An <code>approved_payees</code> table binding each
      landlord and vendor to verified bank details, with <code>record_payment</code> refusing any
      destination not on it. A message-provenance tool exposing real sender and headers rather than
      bare text. And a <strong>Controls / Fraud agent</strong> whose only job is payee and channel
      verification &mdash; separate from Facilities, because the agent that wants the rent paid
      should not also be the agent that certifies where it goes. The same build should add a
      <code>period</code> to <code>payments</code>: the cash-position bug this board exposed existed
      precisely because the schema has no concept of <em>which month's</em> rent was paid.</p>
    </div>

    <div class="card">
      <h3><span class="num">&#8750;</span> The pattern across all three</h3>
      <p>None of these failures are reasoning failures. In every case the agents worked out exactly
      what they did not know and stopped, which is the behaviour you want. The limit is that the
      database only describes the shop's <em>current state</em> &mdash; it records no commitments
      made, no conversations held, and no identities verified. Those three gaps are one gap wearing
      three hats, and the fix is schema and tools, not better prompts.</p>
    </div>
  </div>"""

EXTRA_CSS = """
  .card.grade .mark { float:right; font-size:.64rem; font-weight:800; letter-spacing:.05em;
    text-transform:uppercase; border-radius:999px; padding:.12rem .6rem; }
  .card.grade .mark.strong { background:#ecfdf5; color:#047857; border:1px solid #6ee7b7; }
  .card.grade .mark.mixed  { background:#fffbeb; color:#b45309; border:1px solid #fcd34d; }
  .card.warn { background:#fffbeb; border-color:#fcd34d; }
  .card.warn > h3 { color:#b45309; }
  .card.warn > h3 .num { background:#b45309; }
  .card.gap { border-left:4px solid var(--blue-500); }
  .ev { display:block; margin-top:.3rem; font-size:.78rem; color:var(--muted); font-style:italic; }
  .verdict-line { margin-top:.7rem; padding-top:.6rem; border-top:1px solid var(--blue-100);
    font-weight:600; color:var(--blue-900); }
  .card .lead { font-size:.95rem; }
  .card ul { margin:.4rem 0 .7rem; padding-left:1.2rem; font-size:.86rem; }
  .card ul li { margin-bottom:.35rem; }
</style>"""

page = PAGE.read_text(encoding="utf-8")

marker = '<div role="tabpanel" id="panel-reflection" aria-labelledby="tab-reflection" hidden>'
head, rest = page.split(marker, 1)
after_footer = rest.split("<footer>", 1)[1]

page = f"{head}{marker}\n  {PANEL}\n</div>\n\n<footer>{after_footer}"
page = page.replace("</style>", EXTRA_CSS, 1)

PAGE.write_text(page, encoding="utf-8")
print("reflection tab written")

import { useState } from 'react';
import type { CashResponse } from '../types';

interface Props {
  cash: CashResponse | null;
  onApprove: (body: { kind: string; ref_id: number; amount: number; approved_by: string }) => Promise<void>;
  busy: string | null;
}

/**
 * The human gate. Agents can prepare a payment but never make one — this panel
 * is the only place in the product where cash moves, so it is visually separated
 * from everything the agents produced (amber, not blue) and requires a name.
 */
export default function ApprovalPanel({ cash, onApprove, busy }: Props) {
  const [approver, setApprover] = useState('');

  const items = [
    ...(cash?.open_invoices ?? []).map((i) => ({
      key: `invoice-${i.id}`,
      kind: 'invoice',
      ref_id: i.id,
      amount: i.amount,
      title: `Invoice ${i.id} — ${i.vendor_name}`,
      sub: `due ${i.due_date}`,
    })),
    ...(cash?.leases ?? []).map((l) => ({
      key: `rent-${l.id}`,
      kind: 'rent',
      ref_id: l.id,
      amount: l.monthly_rent,
      title: `Rent — ${l.space_name}`,
      sub: `due ${l.next_due}`,
    })),
  ];

  if (items.length === 0) {
    return (
      <div className="banner success">
        Nothing is awaiting payment — every obligation on file has been settled.
      </div>
    );
  }

  const named = approver.trim().length > 0;
  const balance = cash?.checking_balance ?? 0;

  return (
    <div className="approvals">
      <h3>Waiting on you</h3>
      <p className="why">
        The agents prepared these but cannot pay them. Approving here is the only action in
        this dashboard that moves money, and your name goes onto the ledger row.
      </p>

      <label className="approver-field">
        Approving as
        <input
          value={approver}
          onChange={(e) => setApprover(e.target.value)}
          placeholder="your name"
          aria-label="Name of the person approving"
        />
      </label>
      <p className="approver-note">
        {named ? '' : 'Enter a name to enable approval.'}
      </p>

      {items.map((it) => {
        const affordable = it.amount <= balance;
        const thisBusy = busy === it.key;
        return (
          <div className="approval-row" key={it.key}>
            <div className="approval-what">
              <strong>{it.title}</strong>
              <span>{it.sub}</span>
            </div>
            <div className="approval-amt tnum">
              ${it.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <button
              className="approve-btn"
              disabled={!named || thisBusy || !affordable}
              title={
                !affordable
                  ? 'Checking balance will not cover this'
                  : !named
                    ? 'Enter your name first'
                    : 'Approve and pay'
              }
              onClick={() =>
                onApprove({
                  kind: it.kind,
                  ref_id: it.ref_id,
                  amount: it.amount,
                  approved_by: approver.trim(),
                })
              }
            >
              {thisBusy ? 'Paying…' : affordable ? 'Approve & pay' : 'Insufficient funds'}
            </button>
          </div>
        );
      })}
    </div>
  );
}

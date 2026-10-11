import type { Ticket } from '../types';
import StatusPill from './StatusPill';

interface Props {
  ticket: Ticket;
  selected: boolean;
  running: boolean;
  onSelect: (id: number) => void;
}

/** One ticket in the left rail. The whole card is the hit target. */
export default function TicketCard({ ticket, selected, running, onSelect }: Props) {
  const facts = [
    ticket.sku && `${ticket.sku}${ticket.size ? ` · ${ticket.size}` : ''}`,
    ticket.qty != null && `qty ${ticket.qty}`,
    ticket.invoice_id != null && `invoice ${ticket.invoice_id}`,
    ticket.lease_id != null && `lease ${ticket.lease_id}`,
  ].filter(Boolean) as string[];

  const state = running ? 'running' : ticket.is_resolved ? 'done' : '';

  return (
    <button
      type="button"
      className={`ticket ${selected ? 'selected' : ''} ${state}`}
      onClick={() => onSelect(ticket.id)}
      aria-pressed={selected}
    >
      <div className="ticket-top">
        <span className="ticket-id">#{ticket.id}</span>
        <span className="ticket-type">{ticket.type.replace(/_/g, ' ')}</span>
      </div>
      <h3>{ticket.subject}</h3>
      <p className="requester">{ticket.requester}</p>

      {facts.length > 0 && (
        <div className="ticket-facts">
          {facts.map((f) => (
            <span key={f} className="mono">{f}</span>
          ))}
        </div>
      )}

      <StatusPill status={running ? 'running' : ticket.status} />
    </button>
  );
}

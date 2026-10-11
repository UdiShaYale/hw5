export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  is_open: boolean;
  is_resolved: boolean;
  needs_human: boolean;
}

export interface TicketsResponse {
  count: number;
  open: number;
  resolved: number;
  tickets: Ticket[];
}

export interface AgentSpec {
  key: string;
  name: string;
  title: string;
  accent: string;
  remit: string;
}

export interface OpenInvoice {
  id: number;
  vendor_name: string;
  amount: number;
  due_date: string;
  status: string;
}

export interface Lease {
  id: number;
  space_name: string;
  monthly_rent: number;
  next_due: string;
}

export interface CashResponse {
  checking_balance: number | null;
  as_of: string | null;
  shop_date: string | null;
  committed_outflows: number | null;
  cash_after_commitments: number | null;
  open_invoices: OpenInvoice[];
  leases: Lease[];
}

/** One row in the live feed. `type` decides how it renders. */
export interface AgentEvent {
  run_id: string;
  seq: number;
  ts: string;
  t_ms: number;
  agent: string;
  agent_key: string;
  depth: number;
  type: 'said' | 'tool' | 'delegation' | 'run_started' | 'run_finished';
  // said
  text?: string;
  tools_requested?: string[];
  usage?: { requests: number; input_tokens: number; output_tokens: number };
  // tool
  tool?: string;
  args?: Record<string, unknown>;
  is_write?: boolean;
  blocked?: string;
  result?: string;
  // delegation
  phase?: 'started' | 'done';
  to_agent?: string;
  question?: string;
  reply?: string;
  status?: string;
}

export interface EventsResponse {
  total_events: number;
  returned: number;
  runs: { run_id: string; steps: number; started_at?: string; ended_at?: string }[];
  events: AgentEvent[];
}

export interface Delegation {
  from_agent: string;
  to_agent: string;
  agent_key: string;
  question: string;
  reply: string;
  depth: number;
  status: string;
}

export interface RunResult {
  run_id: string;
  answer: string;
  delegations: Delegation[];
  usage?: {
    model?: string;
    total?: { requests: number; input_tokens: number; output_tokens: number };
    mcp_tool_calls?: number;
    delegations?: number;
  };
  audit_steps?: number;
  error?: string | null;
}

export interface RunStatus {
  run_id: string;
  ticket_id: number;
  status: 'running' | 'done' | 'error';
  result: RunResult | null;
}

export interface PaymentResult {
  ok: boolean;
  payment_id: number;
  kind: string;
  ref_id: number;
  amount: number;
  account: string;
  paid_at: string;
  approved_by: string;
  new_balance: number;
}

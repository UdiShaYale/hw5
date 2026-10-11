import type {
  AgentEvent,
  AgentSpec,
  CashResponse,
  EventsResponse,
  PaymentResult,
  RunStatus,
  TicketsResponse,
} from './types';

/** The FastAPI backend. Plain HTTP — uvicorn is not serving TLS. */
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${API_BASE}. Start it with: uvicorn main:app --reload --port 8000`,
      0,
    );
  }

  if (!res.ok) {
    // FastAPI puts the reason in `detail` — surface it instead of "500".
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join('; ');
    } catch {
      /* keep the status line */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const getTickets = () => request<TicketsResponse>('/tickets');
export const getAgents = () => request<{ agents: AgentSpec[] }>('/agents');
export const getCash = () => request<CashResponse>('/cash');

export const startRun = (ticketId: number) =>
  request<{ run_id: string; ticket_id: number; status: string }>(
    `/tickets/${ticketId}/start`,
    { method: 'POST', body: JSON.stringify({ note: '' }) },
  );

export const getRun = (runId: string) => request<RunStatus>(`/runs/${runId}`);

/** The most recent run that worked this ticket, so history survives a reload. */
export const getTicketHistory = (ticketId: number) =>
  request<{ ticket_id: number; run_id: string | null; runs: string[]; events: AgentEvent[] }>(
    `/tickets/${ticketId}/history`,
  );

export const getEvents = (runId: string, limit = 400) =>
  request<EventsResponse>(`/events?run_id=${encodeURIComponent(runId)}&limit=${limit}`);

export const approvePayment = (body: {
  kind: string;
  ref_id: number;
  amount: number;
  approved_by: string;
  account?: string;
}) => request<PaymentResult>('/approve', { method: 'POST', body: JSON.stringify(body) });

export const resetDatabase = () => request<{ ok: boolean }>('/reset', { method: 'POST' });

export { ApiError };

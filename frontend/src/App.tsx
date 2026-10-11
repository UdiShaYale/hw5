import { useCallback, useEffect, useRef, useState } from 'react';
import './App.css';
import {
  approvePayment,
  getAgents,
  getCash,
  getEvents,
  getRun,
  getTicketHistory,
  getTickets,
  resetDatabase,
  startRun,
} from './api';
import AgentStrip from './components/AgentStrip';
import AgentSummary from './components/AgentSummary';
import ApprovalPanel from './components/ApprovalPanel';
import EventFeed from './components/EventFeed';
import StatusPill from './components/StatusPill';
import TicketCard from './components/TicketCard';
import type { AgentEvent, AgentSpec, CashResponse, RunResult, Ticket } from './types';

const POLL_MS = 1200;

function money(n: number | null | undefined): string {
  if (n == null) return '—';
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [agents, setAgents] = useState<AgentSpec[]>([]);
  const [cash, setCash] = useState<CashResponse | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [runId, setRunId] = useState<string | null>(null);
  const [runningTicket, setRunningTicket] = useState<number | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [historyRunId, setHistoryRunId] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  // Flash the balance when it drops, so an approval is felt and not just logged.
  const [cashDelta, setCashDelta] = useState<number | null>(null);
  const prevBalance = useRef<number | null>(null);

  const refreshTickets = useCallback(async () => {
    const data = await getTickets();
    setTickets(data.tickets);
    setSelectedId((cur) => cur ?? data.tickets[0]?.id ?? null);
  }, []);

  const refreshCash = useCallback(async () => {
    const data = await getCash();
    const prev = prevBalance.current;
    if (prev != null && data.checking_balance != null && data.checking_balance < prev) {
      setCashDelta(data.checking_balance - prev);
      window.setTimeout(() => setCashDelta(null), 1900);
    }
    prevBalance.current = data.checking_balance;
    setCash(data);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [a] = await Promise.all([getAgents(), refreshTickets(), refreshCash()]);
        setAgents(a.agents);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [refreshTickets, refreshCash]);

  // While a run is in flight, pull the feed and watch for completion.
  useEffect(() => {
    if (!runId) return;
    let alive = true;

    const tick = async () => {
      try {
        const [feed, status] = await Promise.all([getEvents(runId), getRun(runId)]);
        if (!alive) return;
        setEvents(feed.events);

        if (status.status !== 'running') {
          setResult(status.result);
          setRunId(null);
          setRunningTicket(null);
          if (status.result?.error) setError(status.result.error);
          // The agents may have changed ticket status and shop state.
          await Promise.all([refreshTickets(), refreshCash()]);
        }
      } catch (e) {
        if (!alive) return;
        setError((e as Error).message);
        setRunId(null);
        setRunningTicket(null);
      }
    };

    void tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [runId, refreshTickets, refreshCash]);

  async function onRun(ticketId: number) {
    setError(null);
    setNotice(null);
    setEvents([]);
    setResult(null);
    try {
      const started = await startRun(ticketId);
      setRunId(started.run_id);
      setRunningTicket(ticketId);
      setHistoryRunId(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onApprove(body: {
    kind: string;
    ref_id: number;
    amount: number;
    approved_by: string;
  }) {
    const key = `${body.kind}-${body.ref_id}`;
    setApproving(key);
    setError(null);
    setNotice(null);
    try {
      const paid = await approvePayment(body);
      setNotice(
        `Paid ${money(paid.amount)} for ${paid.kind} ${paid.ref_id}, approved by ${paid.approved_by}. Checking is now ${money(paid.new_balance)}.`,
      );
      await Promise.all([refreshCash(), refreshTickets()]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApproving(null);
    }
  }

  async function onReset() {
    setResetting(true);
    setError(null);
    setNotice(null);
    try {
      await resetDatabase();
      setEvents([]);
      setResult(null);
      prevBalance.current = null;
      await Promise.all([refreshTickets(), refreshCash()]);
      setNotice('Shop data restored to the original values. The audit trail was left intact.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setResetting(false);
    }
  }

  // Selecting a ticket replays its last run, so a finished ticket does not look
  // like nothing ever happened to it.
  useEffect(() => {
    if (selectedId == null || runId) return;
    let alive = true;
    (async () => {
      try {
        const history = await getTicketHistory(selectedId);
        if (!alive) return;
        setEvents(history.events);
        setResult(null);
        setHistoryRunId(history.run_id);
      } catch {
        /* a ticket with no history is fine — the feed just stays empty */
      }
    })();
    return () => {
      alive = false;
    };
  }, [selectedId, runId]);

  const selected = tickets.find((t) => t.id === selectedId) ?? null;
  const isRunning = runningTicket != null;
  const selectedRunning = isRunning && runningTicket === selected?.id;
  const showResultFor = result && !isRunning;
  const showHistory = !isRunning && !result && events.length > 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">CC</div>
          <div>
            <h1>Campus Customs</h1>
            <p className="sub">
              Agent desk{cash?.shop_date ? ` · shop date ${cash.shop_date}` : ''}
            </p>
          </div>
        </div>

        <dl className={`cash ${cashDelta ? 'dropped' : ''}`}>
          <dt>Checking</dt>
          <dd className="tnum">
            {money(cash?.checking_balance)}
            {cashDelta != null && (
              <span className="cash-delta tnum">{money(cashDelta)}</span>
            )}
          </dd>
          <span className="after tnum">
            {money(cash?.cash_after_commitments)} after what we owe
          </span>
        </dl>

        <button className="ghost-btn" onClick={onReset} disabled={resetting || isRunning}>
          {resetting ? 'Resetting…' : 'Reset shop data'}
        </button>
      </header>

      <div className="layout">
        {/* ---------------- left rail: the queue ---------------- */}
        <aside>
          <div className="col-head">
            <h2>Ticket queue</h2>
            <span className="count tnum">
              {tickets.filter((t) => t.is_open).length} open · {tickets.length} total
            </span>
          </div>
          <div className="ticket-list">
            {tickets.map((t) => (
              <TicketCard
                key={t.id}
                ticket={t}
                selected={t.id === selectedId}
                running={runningTicket === t.id}
                onSelect={setSelectedId}
              />
            ))}
            {tickets.length === 0 && !error && (
              <p style={{ color: 'var(--faint)', fontSize: '0.85rem' }}>Loading tickets…</p>
            )}
          </div>
        </aside>

        {/* ---------------- main: the selected ticket ---------------- */}
        <main className="panel">
          {!selected ? (
            <div className="empty-state">
              <div className="big">🧵</div>
              <p>Pick a ticket from the queue to get started.</p>
            </div>
          ) : (
            <>
              <div className="panel-head">
                <div>
                  <h2>
                    #{selected.id} — {selected.subject}
                  </h2>
                  <p className="meta">
                    {selected.type.replace(/_/g, ' ')} · {selected.requester}
                    {selected.sku ? ` · ${selected.sku}` : ''}
                    {selected.size ? ` size ${selected.size}` : ''}
                    {selected.qty != null ? ` × ${selected.qty}` : ''}
                  </p>
                </div>
                <div className="spacer" />
                <StatusPill status={selectedRunning ? 'running' : selected.status} />
                <button
                  className="run-btn"
                  onClick={() => onRun(selected.id)}
                  disabled={isRunning}
                >
                  {selectedRunning ? 'Agents working…' : 'Run the team'}
                </button>
              </div>

              <div className="panel-body">
                {error && <div className="banner error">{error}</div>}
                {notice && <div className="banner success">{notice}</div>}

                <AgentStrip agents={agents} events={events} running={isRunning} />

                {(events.length > 0 || isRunning) && (
                  <>
                    <div className="feed-head">
                      <h3>Live transcript</h3>
                      {isRunning && <span className="spin" aria-label="running" />}
                      <div className="spacer" />
                      <span className="count tnum" style={{ fontSize: '0.75rem', color: 'var(--faint)' }}>
                        {events.length} events
                      </span>
                    </div>
                    <EventFeed events={events} agents={agents} running={isRunning} />
                  </>
                )}

                {showResultFor && (
                  <>
                    <h3 className="section-title">The Boss&rsquo;s call</h3>
                    <div className="verdict">
                      <h3>Decision</h3>
                      <div className="text">{result.answer}</div>
                      {result.usage && (
                        <div className="verdict-usage tnum">
                          <span>{result.usage.model}</span>
                          <span>{result.usage.delegations ?? 0} delegations</span>
                          <span>{result.usage.mcp_tool_calls ?? 0} tool calls</span>
                          <span>
                            {(result.usage.total?.input_tokens ?? 0).toLocaleString()} in /{' '}
                            {(result.usage.total?.output_tokens ?? 0).toLocaleString()} out tokens
                          </span>
                        </div>
                      )}
                    </div>
                    <AgentSummary agents={agents} events={events} />
                  </>
                )}

                {showHistory && (
                  <AgentSummary
                    agents={agents}
                    events={events}
                    heading={`What each agent did — last run ${historyRunId ?? ''}`}
                  />
                )}

                {selected.needs_human && !isRunning && (
                  <ApprovalPanel cash={cash} onApprove={onApprove} busy={approving} />
                )}

                {selected.notes && (
                  <>
                    <h3 className="section-title">Ticket notes</h3>
                    <div className="notes-block">{selected.notes}</div>
                  </>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

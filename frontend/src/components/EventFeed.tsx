import { useEffect, useRef } from 'react';
import type { AgentEvent, AgentSpec } from '../types';
import { initials } from './AgentStrip';

interface Props {
  events: AgentEvent[];
  agents: AgentSpec[];
  running: boolean;
}

function argSummary(args?: Record<string, unknown>): string {
  if (!args || Object.keys(args).length === 0) return '';
  return Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' ')
    .slice(0, 110);
}

/**
 * The transcript. Three event shapes, three visual treatments, so the eye can
 * tell talking from doing from handing-off without reading every line:
 *   said       — plain card, the agent's own words
 *   tool       — tinted card with the tool name; amber if it wrote, red if blocked
 *   delegation — dashed card with an arrow
 */
export default function EventFeed({ events, agents, running }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);

  // Follow the tail while running, but stop fighting the user if they scroll up.
  useEffect(() => {
    const el = ref.current;
    if (!el || !pinned.current) return;
    el.scrollTop = el.scrollHeight;
  }, [events.length]);

  function onScroll() {
    const el = ref.current;
    if (!el) return;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  }

  const accentOf = (key: string) =>
    agents.find((a) => a.key === key)?.accent ?? 'var(--blue-600)';

  if (events.length === 0) {
    return (
      <div className="feed" ref={ref}>
        <p style={{ color: 'var(--faint)', fontSize: '0.85rem', margin: '1rem auto' }}>
          {running ? 'Waiting for the first agent step…' : 'No activity yet. Press Run the team.'}
        </p>
      </div>
    );
  }

  return (
    <div className="feed" ref={ref} onScroll={onScroll} role="log" aria-live="polite">
      {events.map((e) => {
        const accent = accentOf(e.agent_key);
        const time = `${(e.t_ms / 1000).toFixed(1)}s`;

        if (e.type === 'run_started' || e.type === 'run_finished') {
          return (
            <div className="event milestone" key={e.seq} style={{ ['--accent' as string]: accent }}>
              <div className="av">★</div>
              <div className="event-body">
                <div className="event-meta">
                  <span className="who">
                    {e.type === 'run_started' ? 'Run started' : 'Run finished'}
                  </span>
                  <span className="t tnum">{time}</span>
                </div>
              </div>
            </div>
          );
        }

        if (e.type === 'tool') {
          const blocked = Boolean(e.blocked);
          return (
            <div
              className={`event tool ${e.is_write ? 'write' : ''} ${blocked ? 'blocked' : ''}`}
              key={e.seq}
              style={{ ['--accent' as string]: accent }}
            >
              <div className="av">{initials(e.agent)}</div>
              <div className="event-body">
                <div className="event-meta">
                  <span className="who">{e.agent}</span>
                  {e.is_write && !blocked && <span className="badge-write">WRITE</span>}
                  {blocked && <span className="badge-block">BLOCKED</span>}
                  {e.depth > 0 && <span className="depth">d{e.depth}</span>}
                  <span className="t tnum">{time}</span>
                </div>
                <div className="event-text">
                  <span className="tool-name mono">{e.tool}</span>{' '}
                  <span className="tool-args mono">{argSummary(e.args)}</span>
                </div>
                {blocked && <div className="event-text" style={{ marginTop: 4 }}>{e.blocked}</div>}
              </div>
            </div>
          );
        }

        if (e.type === 'delegation') {
          return (
            <div className="event delegation" key={e.seq} style={{ ['--accent' as string]: accent }}>
              <div className="av">{initials(e.agent)}</div>
              <div className="event-body">
                <div className="event-meta">
                  <span className="who">
                    {e.agent} <span className="arrow">→</span> {e.to_agent}
                  </span>
                  {e.depth > 0 && <span className="depth">d{e.depth}</span>}
                  <span className="t tnum">{time}</span>
                </div>
                <div className="event-text">
                  {e.phase === 'started'
                    ? e.question
                    : `${e.to_agent} reported back${e.status === 'error' ? ' (error)' : ''}.`}
                </div>
              </div>
            </div>
          );
        }

        // said
        return (
          <div className="event said" key={e.seq} style={{ ['--accent' as string]: accent }}>
            <div className="av">{initials(e.agent)}</div>
            <div className="event-body">
              <div className="event-meta">
                <span className="who">{e.agent}</span>
                {e.depth > 0 && <span className="depth">d{e.depth}</span>}
                <span className="t tnum">{time}</span>
              </div>
              <div className="event-text">{e.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

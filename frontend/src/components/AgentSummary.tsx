import type { AgentEvent, AgentSpec } from '../types';
import { initials } from './AgentStrip';

interface Props {
  agents: AgentSpec[];
  events: AgentEvent[];
  /** Heading to show above the cards. Pass null when the caller renders its own. */
  heading?: string | null;
}

/**
 * After the run: one card per agent that actually did something, with its
 * closing statement and the tools it used. The point is to answer "what did
 * each agent contribute" without scrolling the whole transcript back.
 */
export default function AgentSummary({ agents, events, heading = 'What each agent did' }: Props) {
  const active = agents
    .map((a) => {
      const mine = events.filter((e) => e.agent_key === a.key);
      const tools = [...new Set(mine.filter((e) => e.type === 'tool' && !e.blocked).map((e) => e.tool!))];
      const writes = mine.filter((e) => e.type === 'tool' && e.is_write && !e.blocked).length;
      const asked = mine.filter((e) => e.type === 'delegation' && e.phase === 'started').length;
      // The agent's last substantive statement is its conclusion.
      const spoke = mine.filter((e) => e.type === 'said' && (e.text ?? '').trim().length > 24);
      const closing = spoke.length ? spoke[spoke.length - 1].text!.trim() : '';
      return { a, count: mine.length, tools, writes, asked, closing };
    })
    .filter((x) => x.count > 0);

  if (active.length === 0) return null;

  return (
    <>
      {heading && <h3 className="section-title">{heading}</h3>}
      <div className="summary-grid">
        {active.map(({ a, tools, writes, asked, closing }) => (
          <div key={a.key} className="summary-card" style={{ ['--accent' as string]: a.accent }}>
            <h4>
              <span
                className="agent-avatar"
                style={{ width: 20, height: 20, fontSize: '0.6rem', background: a.accent }}
              >
                {initials(a.name)}
              </span>
              {a.name}
            </h4>
            <div className="did tnum">
              <span>{tools.length} tools</span>
              {asked > 0 && <span>{asked} delegated</span>}
              {writes > 0 && <span style={{ color: 'var(--amber)' }}>{writes} writes</span>}
            </div>
            <p>
              {closing
                ? closing.length > 300
                  ? `${closing.slice(0, 300)}…`
                  : closing
                : 'Gathered facts and reported back to the Boss.'}
            </p>
            {tools.length > 0 && (
              <div className="tools">
                {tools.map((t) => (
                  <code key={t}>{t}</code>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

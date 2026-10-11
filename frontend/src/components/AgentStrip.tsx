import type { AgentEvent, AgentSpec } from '../types';

interface Props {
  agents: AgentSpec[];
  events: AgentEvent[];
  running: boolean;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase();
}

/**
 * The team at a glance: one chip per agent, lit up when that agent is the one
 * currently working. Answers "who is doing something right now" without making
 * anyone read the feed.
 */
export default function AgentStrip({ agents, events, running }: Props) {
  const lastAgent = events.length ? events[events.length - 1].agent_key : null;

  return (
    <div className="agent-strip">
      {agents.map((a) => {
        const mine = events.filter((e) => e.agent_key === a.key);
        const tools = mine.filter((e) => e.type === 'tool');
        const said = mine.filter((e) => e.type === 'said' && e.text);
        const isActive = running && lastAgent === a.key;
        const touched = mine.length > 0;

        // What this agent did most recently, in plain words.
        const latest = [...mine].reverse()[0];
        let doing = '';
        if (latest?.type === 'tool') doing = `called ${latest.tool}`;
        else if (latest?.type === 'delegation')
          doing = latest.phase === 'started' ? `asked ${latest.to_agent}` : `heard back`;
        else if (latest?.type === 'said' && latest.text) doing = 'reported';

        return (
          <div
            key={a.key}
            className={[
              'agent-chip',
              a.key === 'boss' ? 'boss' : '',
              isActive ? 'active' : touched ? '' : 'idle',
            ].join(' ')}
            style={{ ['--accent' as string]: a.accent }}
            title={a.remit}
          >
            <div className="agent-head">
              <div className="agent-avatar">{initials(a.name)}</div>
              <div>
                <div className="agent-name">{a.name}</div>
                <div className="agent-title">{a.title}</div>
              </div>
            </div>
            <div className="agent-stat tnum">
              <span>{tools.length} tools</span>
              <span>{said.length} notes</span>
            </div>
            {isActive && doing && <div className="agent-doing">{doing}…</div>}
          </div>
        );
      })}
    </div>
  );
}

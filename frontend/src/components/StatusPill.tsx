const LABELS: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  needs_human: 'Needs you',
  resolved: 'Resolved',
  cancelled: 'Cancelled',
  running: 'Agents working',
};

/** Status reads the same everywhere: one pill, one vocabulary. */
export default function StatusPill({ status }: { status: string }) {
  const label = LABELS[status] ?? status;
  const animated = status === 'running';
  return (
    <span className={`pill ${status}`}>
      {(animated || status === 'needs_human') && <span className="dot" />}
      {label}
    </span>
  );
}

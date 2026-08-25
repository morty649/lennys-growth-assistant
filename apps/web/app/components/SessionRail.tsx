import type { ProviderConfig, Session } from '../contracts';

type SessionRailProps = {
  sessions: Session[];
  activeId: string;
  providerState?: ProviderConfig;
  railOpen: boolean;
  onOpenRail: () => void;
  onCloseRail: () => void;
  onCreateSession: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
};

export function SessionRail({
  sessions,
  activeId,
  providerState,
  railOpen,
  onOpenRail,
  onCloseRail,
  onCreateSession,
  onSelectSession,
  onDeleteSession,
}: SessionRailProps) {
  return (
    <>
      <button
        className="mobile-menu"
        onClick={onOpenRail}
        type="button"
        aria-label="Open sessions"
      >
        L/G_
      </button>
      <aside className={`session-rail ${railOpen ? 'open' : ''}`}>
        <button
          className="rail-close"
          onClick={onCloseRail}
          type="button"
          aria-label="Close sessions"
        >
          ×
        </button>
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">L/G_</div>
          <div>
            <div className="brand-name">Lenny&apos;s Growth</div>
            <div className="brand-subtitle">podcast intelligence</div>
          </div>
        </div>
        <button className="new-session" onClick={onCreateSession} type="button">
          + new investigation
        </button>
        <div className="rail-label">Private sessions</div>
        <nav aria-label="Chat sessions" className="session-list">
          {sessions.map((session) => (
            <div
              className={session.id === activeId ? 'session-row active' : 'session-row'}
              key={session.id}
            >
              <button
                className="session-select"
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <span className="session-node" aria-hidden="true" />
                <span className="session-title">{session.title}</span>
              </button>
              <button
                className="session-delete"
                onClick={(event) => {
                  event.stopPropagation();
                  onDeleteSession(session.id);
                }}
                type="button"
                aria-label={`Delete ${session.title}`}
              >
                ×
              </button>
            </div>
          ))}
        </nav>
        <div className="rail-footer">
          <span
            className={`status-dot ${providerState?.enabled ? 'ready' : 'unavailable'}`}
            aria-hidden="true"
          />
          assistant · {providerState?.enabled ? 'ready' : (providerState?.availability ?? 'checking')}
        </div>
      </aside>
    </>
  );
}

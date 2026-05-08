// HUD Topbar — persistent top navigation strip.
// Port of prototype/shared.jsx Topbar, adapted for react-router-dom.
//
// Active link detection uses useLocation; routes match the post-rebuild URLs:
//   /intel /scanner /bot /training /settings /journal
// During Phase 2 the new routes don't all exist yet — clicks may 404 until
// Phase 3 lands the page ports. That's expected.
//
// PhemexStatusPill is mounted in the right-rail; landing in Phase 2d.
import { useEffect, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Chip } from './Chip';

interface NavLink {
  id: string;
  label: string;
  to: string;
  /** routes considered "this nav item is active" */
  matchPrefixes?: string[];
}

const LINKS: NavLink[] = [
  { id: 'intel', label: 'Intel', to: '/intel' },
  { id: 'scanner', label: 'Scanner', to: '/scanner', matchPrefixes: ['/scanner', '/scan', '/results'] },
  { id: 'bot', label: 'Bot', to: '/bot', matchPrefixes: ['/bot'] },
  { id: 'training', label: 'Training', to: '/training' },
  { id: 'settings', label: 'Risk', to: '/settings' },
  { id: 'journal', label: 'Journal', to: '/journal' },
];

interface TopbarProps {
  /** Slot for the persistent Phemex pill (Phase 2d). */
  rightSlot?: ReactNode;
  /** Active scanner mode badge slot (e.g. STEALTH, OVERWATCH). */
  modeSlot?: ReactNode;
}

function isActive(pathname: string, link: NavLink): boolean {
  const prefixes = link.matchPrefixes || [link.to];
  return prefixes.some((p) => pathname === p || pathname.startsWith(p + '/'));
}

function useUtcClock(): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  // Returns HH:MM:SS UTC
  return new Date(now).toISOString().slice(11, 19);
}

export function Topbar({ rightSlot, modeSlot }: TopbarProps) {
  const { pathname } = useLocation();
  const utc = useUtcClock();

  return (
    <div className="topbar">
      <Link
        to="/"
        className="brand"
        style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: 14 }}
      >
        <div className="brand-mark">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="var(--accent)" strokeWidth="1.5" />
            <circle cx="12" cy="12" r="3" fill="var(--accent)" />
            <line x1="12" y1="1" x2="12" y2="6" stroke="var(--accent)" strokeWidth="1.5" />
            <line x1="12" y1="18" x2="12" y2="23" stroke="var(--accent)" strokeWidth="1.5" />
            <line x1="1" y1="12" x2="6" y2="12" stroke="var(--accent)" strokeWidth="1.5" />
            <line x1="18" y1="12" x2="23" y2="12" stroke="var(--accent)" strokeWidth="1.5" />
          </svg>
        </div>
        <div>
          <div className="brand-name">SniperSight</div>
          <div className="brand-sub">Tactical Trading HUD</div>
        </div>
      </Link>

      <nav className="nav">
        {LINKS.map((l) => (
          <Link key={l.id} to={l.to} className={isActive(pathname, l) ? 'active' : ''}>
            {l.label}
          </Link>
        ))}
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {modeSlot}
        {rightSlot}
        <Chip>UTC {utc}</Chip>
      </div>
    </div>
  );
}

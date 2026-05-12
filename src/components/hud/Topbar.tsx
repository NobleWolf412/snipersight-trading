// HUD Topbar — persistent top navigation strip.
// Port of prototype/shared.jsx Topbar, adapted for react-router-dom.
//
// Active link detection uses useLocation; routes match the post-rebuild URLs:
//   /intel /scanner /bot /training /settings /journal
//
// Phase 3 follow-up 3z.g — mobile responsive chrome. At ≤700px the topbar
// collapses to logo + hamburger; the nav cluster (links + mode badge +
// Phemex pill + UTC clock) moves into a slide-in drawer from the right.
// Drawer closes automatically on route change + body scroll is locked
// while open. Drawer backdrop is click-to-close. Desktop layout (>700px)
// is unchanged: nav remains inline, hamburger is display:none via CSS.
//
// Direction-agnostic per CLAUDE.md §10 #3: the topbar is presentational
// chrome with no directional state; the drawer toggle has no long/short
// branch.
//
// PhemexStatusPill mounted via rightSlot. Active scanner mode via modeSlot.
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
  { id: 'scanner', label: 'Scanner', to: '/scanner', matchPrefixes: ['/scanner'] },
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

  // 3z.g: mobile drawer state. Hamburger toggles, route change closes,
  // backdrop click closes, ESC key closes.
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Auto-close on route change.
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  // Body scroll lock while drawer is open. Cleanup restores scroll
  // on unmount AND on drawer close (StrictMode-safe).
  useEffect(() => {
    if (!drawerOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onKey);
    };
  }, [drawerOpen]);

  const navList = (
    <nav className="nav">
      {LINKS.map((l) => (
        <Link key={l.id} to={l.to} className={isActive(pathname, l) ? 'active' : ''}>
          {l.label}
        </Link>
      ))}
    </nav>
  );

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

      {/* Desktop nav cluster — hidden by CSS at ≤700px */}
      {navList}

      <div className="topbar-right">
        {modeSlot}
        {rightSlot}
        <Chip className="utc-chip">UTC {utc}</Chip>
      </div>

      {/* 3z.g: Hamburger button — hidden by CSS on desktop. */}
      <button
        type="button"
        className="hamburger"
        aria-label={drawerOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={drawerOpen}
        aria-controls="mobile-drawer"
        onClick={() => setDrawerOpen((v) => !v)}
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          {drawerOpen ? (
            <>
              <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </>
          ) : (
            <>
              <line x1="4" y1="7" x2="20" y2="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <line x1="4" y1="17" x2="20" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </>
          )}
        </svg>
      </button>

      {/* 3z.g: Mobile drawer backdrop. display:block via .open class. */}
      <div
        className={`mobile-drawer-backdrop${drawerOpen ? ' open' : ''}`}
        onClick={() => setDrawerOpen(false)}
        aria-hidden="true"
      />

      {/* 3z.g: Mobile drawer. Slide-in via transform. */}
      <aside
        id="mobile-drawer"
        className={`mobile-drawer${drawerOpen ? ' open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
      >
        <div className="mobile-drawer-head">
          <span className="mono mobile-drawer-title">NAVIGATION</span>
          <button
            type="button"
            className="mobile-drawer-close"
            aria-label="Close menu"
            onClick={() => setDrawerOpen(false)}
          >
            ×
          </button>
        </div>
        <nav className="mobile-drawer-nav">
          {LINKS.map((l) => (
            <Link
              key={l.id}
              to={l.to}
              className={isActive(pathname, l) ? 'active' : ''}
              onClick={() => setDrawerOpen(false)}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="mobile-drawer-aux">
          {modeSlot}
          {rightSlot}
          <Chip>UTC {utc}</Chip>
        </div>
      </aside>
    </div>
  );
}

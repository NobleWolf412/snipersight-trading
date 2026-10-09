import { useEffect,useRef,useState,type ReactNode } from 'react';
import { Link,useLocation } from 'react-router-dom';
import { Chip } from './Chip';
import { lockDialogScroll } from './dialogScrollLock';

const LINKS = [
  { label: 'Scanner', to: '/scanner' },
  { label: 'Bot', to: '/bot' },
  { label: 'Journal', to: '/journal' },
  { label: 'Intel', to: '/intel' },
  { label: 'Training', to: '/training' },
  { label: 'Settings', to: '/settings' },
];

interface TopbarProps {
  rightSlot?: ReactNode;
  modeSlot?: ReactNode;
}

function useUtcClock(): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return new Date(now).toISOString().slice(11, 19);
}

export function Topbar({ rightSlot, modeSlot }: TopbarProps) {
  const { pathname } = useLocation();
  const utc = useUtcClock();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawer = useRef<HTMLDialogElement>(null);

  useEffect(() => { setDrawerOpen(false); }, [pathname]);
  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 1121px)');
    const closeOnDesktop = () => { if (desktop.matches) setDrawerOpen(false); };
    desktop.addEventListener('change', closeOnDesktop);
    return () => desktop.removeEventListener('change', closeOnDesktop);
  }, []);
  useEffect(() => {
    const dialog = drawer.current;
    if (!dialog) return;
    if (!drawerOpen) {
      if (dialog.open) dialog.close();
      return;
    }
    // Native modal dialog owns focus containment, inert background and restoration.
    dialog.showModal();
    const release = lockDialogScroll();
    return () => {
      if (dialog.open) dialog.close();
      release();
    };
  }, [drawerOpen]);

  const links = (mobile = false) => LINKS.map(link => {
    const active = pathname === link.to || pathname.startsWith(link.to + '/');
    return <Link key={link.to} to={link.to} className={active ? 'active' : ''}
      aria-current={active ? 'page' : undefined}
      onClick={mobile ? () => setDrawerOpen(false) : undefined}>{link.label}</Link>;
  });

  return (
    <header className="topbar">
      <Link to="/" className="brand" aria-label="SniperSight home">
        <span className="brand-mark" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="var(--accent)" strokeWidth="1.5" />
            <circle cx="12" cy="12" r="3" fill="var(--accent)" />
            <path d="M12 1v5m0 12v5M1 12h5m12 0h5" stroke="var(--accent)" strokeWidth="1.5" />
          </svg>
        </span>
        <span>
          <span className="brand-name">SniperSight</span>
          <span className="brand-sub">Trading workspace</span>
        </span>
      </Link>
      <nav className="nav" aria-label="Primary">{links()}</nav>
      <div className="topbar-right">{modeSlot}{rightSlot}<Chip className="utc-chip">UTC {utc}</Chip></div>
      <button type="button" className="hamburger" aria-label="Open menu"
        aria-expanded={drawerOpen} aria-controls="mobile-drawer" onClick={() => setDrawerOpen(true)}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <dialog ref={drawer} id="mobile-drawer" className="mobile-drawer" aria-label="Navigation menu"
        onCancel={event => { event.preventDefault(); setDrawerOpen(false); }}
        onClose={event => { if (event.target === event.currentTarget) setDrawerOpen(false); }}
        onClick={event => { if (event.target === event.currentTarget) setDrawerOpen(false); }}>
        <div className="mobile-drawer-head">
          <span className="mobile-drawer-title">Navigation</span>
          <button type="button" className="mobile-drawer-close" aria-label="Close menu"
            onClick={() => setDrawerOpen(false)}>×</button>
        </div>
        <nav className="mobile-drawer-nav" aria-label="Primary">{links(true)}</nav>
        <div className="mobile-drawer-aux">{modeSlot}{rightSlot}<Chip>UTC {utc}</Chip></div>
      </dialog>
    </header>
  );
}

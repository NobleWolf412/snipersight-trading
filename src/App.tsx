import { useBrowserPreferences } from '@/services/browserPreferences';
// Route pages load on demand; shell imports stay explicit.
import { Suspense, lazy } from 'react';
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { SniperReticle } from '@/components/SniperReticle';
import { Topbar } from '@/components/hud/Topbar';
import { TacticalBgDom } from '@/components/hud/TacticalBgDom';
import { PhemexStatusPill } from '@/components/hud/PhemexStatusPill';
import { ActiveModeBadge } from '@/components/hud/ActiveModeBadge';
import { ActiveScanBeacon } from '@/components/ActiveScanBeacon/ActiveScanBeacon';

const Landing = lazy(() => import('@/pages/Landing').then((m) => ({ default: m.Landing })));
const Scanner = lazy(() => import('@/pages/Scanner').then((m) => ({ default: m.Scanner })));
const BotIndex = lazy(() => import('@/pages/BotIndex').then((m) => ({ default: m.BotIndex })));
const BotSetup = lazy(() => import('@/pages/BotSetup').then((m) => ({ default: m.BotSetup })));
const BotStatus = lazy(() => import('@/pages/BotStatus').then((m) => ({ default: m.BotStatus })));
const TrainingGround = lazy(() =>
  import('@/pages/TrainingGround').then((m) => ({ default: m.TrainingGround })),
);
const RangeBot = lazy(() =>
  import('@/pages/training/RangeBot').then((m) => ({ default: m.RangeBot })),
);
const Drills = lazy(() =>
  import('@/pages/training/Drills').then((m) => ({ default: m.Drills })),
);
const Replay = lazy(() =>
  import('@/pages/training/Replay').then((m) => ({ default: m.Replay })),
);
const Lessons = lazy(() =>
  import('@/pages/training/Lessons').then((m) => ({ default: m.Lessons })),
);
const Intel = lazy(() => import('@/pages/Intel').then((m) => ({ default: m.Intel })));
const TradeJournal = lazy(() =>
  import('@/pages/TradeJournal').then((m) => ({ default: m.TradeJournal })),
);
const Settings = lazy(() => import('@/pages/Settings').then((m) => ({ default: m.Settings })));

function LoadingFallback() {
  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--fg)',
      }}
    >
      <div className="hud" style={{ fontSize: 13, color: 'var(--accent)' }}>
        Loading workspace…
      </div>
    </div>
  );
}

function App() {
  const preferences = useBrowserPreferences();
  const { pathname } = useLocation();
  return (
    <>
      {preferences.tacticalBackground && <TacticalBgDom />}
      {preferences.reticle && <SniperReticle />}
      <a className="skip-link" href="#workspace-content">Skip to content</a>
      <div className={pathname === '/' ? 'shell' : 'shell workspace'}>
        <Topbar modeSlot={<ActiveModeBadge />} rightSlot={<PhemexStatusPill />} />
        <main id="workspace-content" tabIndex={-1}>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/scanner" element={<Scanner />} />
              <Route path="/bot" element={<BotIndex />} />
              <Route path="/bot/setup" element={<BotSetup />} />
              <Route path="/bot/status" element={<BotStatus />} />
              <Route path="/training" element={<TrainingGround />} />
              <Route path="/training/range" element={<RangeBot />} />
              <Route path="/training/drills" element={<Drills />} />
              <Route path="/training/replay" element={<Replay />} />
              <Route path="/training/lessons" element={<Lessons />} />
              <Route path="/intel" element={<Intel />} />
              <Route path="/journal" element={<TradeJournal />} />
              <Route path="/settings" element={<Settings />} />
              {['/scan', '/results', '/scanner/setup', '/scanner/status'].map(path =>
                <Route key={path} path={path} element={<Navigate to="/scanner" replace />} />)}
              {['/market', '/htf'].map(path => <Route key={path} path={path} element={<Navigate to="/intel" replace />} />)}
              <Route path="*" element={<div className="page"><h1>Page not found</h1><Link to="/">Return home</Link> · <Link to="/scanner">Open scanner</Link></div>} />
            </Routes>
          </Suspense>
        </main>
      </div>
      <ActiveScanBeacon />
    </>
  );
}

export default App;

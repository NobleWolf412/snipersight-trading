// App shell — Phase 2e wiring.
// Replaced the legacy <TopBar /> with the new HUD <Topbar />, which renders
// the persistent <PhemexStatusPill /> in its right rail. The legacy
// <TacticalBackground /> is replaced by <TacticalBgDom /> (CSS-driven layers).
// The shadcn <Toaster /> is kept for now; Phase 7 will replace with a HUD
// flash banner once shadcn primitives are removed.
//
// Pages still resolve to their existing TSX files. Phase 3 swaps each page
// in turn to a HUD-styled rewrite.

import { Suspense, lazy } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { Routes, Route } from 'react-router-dom';
import { SniperReticle } from '@/components/SniperReticle';
import { Topbar, TacticalBgDom, PhemexStatusPill } from '@/components/hud';
import { ActiveScanBeacon } from '@/components/ActiveScanBeacon/ActiveScanBeacon';

const Landing = lazy(() => import('@/pages/Landing').then((m) => ({ default: m.Landing })));
const ScannerSetup = lazy(() =>
  import('@/pages/ScannerSetup').then((m) => ({ default: m.ScannerSetup })),
);
const BotSetup = lazy(() => import('@/pages/BotSetup').then((m) => ({ default: m.BotSetup })));
const ScannerStatus = lazy(() =>
  import('@/pages/ScannerStatus').then((m) => ({ default: m.ScannerStatus })),
);
const BotStatus = lazy(() => import('@/pages/BotStatus').then((m) => ({ default: m.BotStatus })));
const ScanResults = lazy(() =>
  import('@/pages/ScanResults').then((m) => ({ default: m.ScanResults })),
);
const TrainingGround = lazy(() =>
  import('@/pages/TrainingGround').then((m) => ({ default: m.TrainingGround })),
);
const MarketOverview = lazy(() =>
  import('@/pages/MarketOverview').then((m) => ({ default: m.MarketOverview })),
);
const Intel = lazy(() => import('@/pages/Intel').then((m) => ({ default: m.Intel })));
const HTFOpportunities = lazy(() =>
  import('@/pages/HTFOpportunities').then((m) => ({ default: m.HTFOpportunities })),
);
const TradeJournal = lazy(() =>
  import('@/pages/TradeJournal').then((m) => ({ default: m.TradeJournal })),
);
const Settings = lazy(() => import('@/pages/Settings').then((m) => ({ default: m.Settings })));

function LoadingFallback() {
  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100vw',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--fg)',
      }}
    >
      <div className="hud" style={{ fontSize: 13, color: 'var(--accent)' }}>
        Loading tactical systems…
      </div>
    </div>
  );
}

function App() {
  return (
    <>
      <TacticalBgDom />
      <SniperReticle />
      <div className="shell">
        <Topbar rightSlot={<PhemexStatusPill />} />
        <main>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/scanner/setup" element={<ScannerSetup />} />
              <Route path="/scanner/status" element={<ScannerStatus />} />
              <Route path="/scan" element={<ScannerSetup />} />
              <Route path="/results" element={<ScanResults />} />
              <Route path="/bot/setup" element={<BotSetup />} />
              <Route path="/bot/status" element={<BotStatus />} />
              <Route path="/training" element={<TrainingGround />} />
              <Route path="/market" element={<MarketOverview />} />
              <Route path="/intel" element={<Intel />} />
              <Route path="/htf" element={<HTFOpportunities />} />
              <Route path="/journal" element={<TradeJournal />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Suspense>
        </main>
      </div>
      <ActiveScanBeacon />
      <Toaster />
    </>
  );
}

export default App;

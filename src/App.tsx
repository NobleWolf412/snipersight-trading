// App shell — Phase 2e wiring + Phase 6 sub-step 1 archive.
// Replaced the legacy <TopBar /> with the new HUD <Topbar />, which renders
// the persistent <PhemexStatusPill /> in its right rail. The legacy
// <TacticalBackground /> is replaced by <TacticalBgDom /> (CSS-driven layers).
// The shadcn <Toaster /> is kept for now; Phase 7 will replace with a HUD
// flash banner once shadcn primitives are removed.
//
// Phase 6 sub-step 1: legacy routes dropped (`/scanner/setup`, `/scanner/status`,
// `/scan`, `/results`, `/market`, `/htf`). These pointed to the pre-rewrite
// pages (ScannerSetup, ScannerStatus, ScanResults, MarketOverview,
// HTFOpportunities) which are slated for archive in sub-step 2. Their
// functions are now subsumed by `/scanner` and `/intel` in the HUD-rebuilt
// page set.

import { Suspense, lazy } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { Routes, Route } from 'react-router-dom';
import { SniperReticle } from '@/components/SniperReticle';
import { Topbar, TacticalBgDom, PhemexStatusPill } from '@/components/hud';
import { ActiveScanBeacon } from '@/components/ActiveScanBeacon/ActiveScanBeacon';

const Landing = lazy(() => import('@/pages/Landing').then((m) => ({ default: m.Landing })));
const Scanner = lazy(() => import('@/pages/Scanner').then((m) => ({ default: m.Scanner })));
const BotSetup = lazy(() => import('@/pages/BotSetup').then((m) => ({ default: m.BotSetup })));
const BotStatus = lazy(() => import('@/pages/BotStatus').then((m) => ({ default: m.BotStatus })));
const TrainingGround = lazy(() =>
  import('@/pages/TrainingGround').then((m) => ({ default: m.TrainingGround })),
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
              <Route path="/scanner" element={<Scanner />} />
              <Route path="/bot/setup" element={<BotSetup />} />
              <Route path="/bot/status" element={<BotStatus />} />
              <Route path="/training" element={<TrainingGround />} />
              <Route path="/intel" element={<Intel />} />
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

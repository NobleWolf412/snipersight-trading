import { Suspense, lazy } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { Routes, Route } from 'react-router-dom';
import { SniperReticle } from '@/components/SniperReticle';

const Landing = lazy(() => import('@/pages/Landing').then(m => ({ default: m.Landing })));
const ScannerSetup = lazy(() => import('@/pages/ScannerSetup').then(m => ({ default: m.ScannerSetup })));
const BotSetup = lazy(() => import('@/pages/BotSetup').then(m => ({ default: m.BotSetup })));
const ScannerStatus = lazy(() => import('@/pages/ScannerStatus').then(m => ({ default: m.ScannerStatus })));
const BotStatus = lazy(() => import('@/pages/BotStatus').then(m => ({ default: m.BotStatus })));
const ScanResults = lazy(() => import('@/pages/ScanResults').then(m => ({ default: m.ScanResults })));
const TrainingGround = lazy(() => import('@/pages/TrainingGround').then(m => ({ default: m.TrainingGround })));
const MarketOverview = lazy(() => import('@/pages/MarketOverview').then(m => ({ default: m.MarketOverview })));
const Intel = lazy(() => import('@/pages/Intel').then(m => ({ default: m.Intel })));

function LoadingFallback() {
  return (
    <div className="min-h-screen w-screen bg-background text-foreground flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
        <div className="text-sm text-muted-foreground heading-hud">LOADING TACTICAL SYSTEMS...</div>
      </div>
    </div>
  );
}

function App() {
  console.log('[App] Rendering App component');
  
  return (
    <div className="min-h-screen w-screen bg-background text-foreground">
      <SniperReticle />
      <main className="w-full h-full tactical-grid">
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
          </Routes>
        </Suspense>
      </main>
      <Toaster />
    </div>
  );
}

export default App;

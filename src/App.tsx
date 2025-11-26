import { Toaster } from '@/components/ui/sonner';
import { Landing } from '@/pages/Landing';
import { ScannerSetup } from '@/pages/ScannerSetup';
import { BotSetup } from '@/pages/BotSetup';
import { ScannerStatus } from '@/pages/ScannerStatus';
import { BotStatus } from '@/pages/BotStatus';
import { ScanResults } from '@/pages/ScanResults';
import { TrainingGround } from '@/pages/TrainingGround';
import { MarketOverview } from '@/pages/MarketOverview';
import { Intel } from '@/pages/Intel';
import { Routes, Route } from 'react-router-dom';
import { SniperReticle } from '@/components/SniperReticle';

function App() {
  return (
    <div className="min-h-screen w-screen bg-background text-foreground">
      <SniperReticle />
      <main className="w-full h-full tactical-grid">
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
      </main>
      <Toaster />
    </div>
  );
}

export default App;

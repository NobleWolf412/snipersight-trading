import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { ScannerProvider } from '@/context/ScannerContext';
import { WalletProvider } from '@/context/WalletContext';
import { TopBar } from '@/components/TopBar/TopBar';
import { Landing } from '@/pages/Landing';
import { ScannerSetup } from '@/pages/ScannerSetup';
import { ScanResults } from '@/pages/ScanResults';
import { BotSetup } from '@/pages/BotSetup';
import { BotStatus } from '@/pages/BotStatus';
import { MarketOverview } from '@/pages/MarketOverview';
import { Intel } from '@/pages/Intel';
import { TrainingGround } from '@/pages/TrainingGround';

function App() {
  return (
    <BrowserRouter>
      <WalletProvider>
        <ScannerProvider>
          <div className="min-h-screen bg-background text-foreground tactical-grid">
            <TopBar />
            <main>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/scanner/setup" element={<ScannerSetup />} />
                <Route path="/scanner/results" element={<ScanResults />} />
                <Route path="/bot/setup" element={<BotSetup />} />
                <Route path="/bot/status" element={<BotStatus />} />
                <Route path="/market" element={<MarketOverview />} />
                <Route path="/intel" element={<Intel />} />
                <Route path="/training" element={<TrainingGround />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
            <Toaster />
          </div>
        </ScannerProvider>
      </WalletProvider>
    </BrowserRouter>
  );
}

export default App;

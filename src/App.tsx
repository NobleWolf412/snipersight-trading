import { Toaster } from '@/components/ui/sonner';
import { Landing } from '@/pages/Landing';
import { ScannerSetup } from '@/pages/ScannerSetup';
import { BotSetup } from '@/pages/BotSetup';
import { ScannerStatus } from '@/pages/ScannerStatus';
import { BotStatus } from '@/pages/BotStatus';
import { Routes, Route } from 'react-router-dom';

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground tactical-grid">
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/scanner/setup" element={<ScannerSetup />} />
          <Route path="/scanner/status" element={<ScannerStatus />} />
          <Route path="/bot/setup" element={<BotSetup />} />
          <Route path="/bot/status" element={<BotStatus />} />
        </Routes>
      </main>
      <Toaster />
    </div>
  );
}

export default App;

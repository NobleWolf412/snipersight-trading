import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ScannerProvider } from '@/context/ScannerContext';
import { WalletProvider } from '@/context/WalletContext';
import { Navigation } from '@/components/Navigation/Navigation';
import { Landing } from '@/pages/Landing';
import { ScannerSetup } from '@/pages/ScannerSetup';
import { ScanResults } from '@/pages/ScanResults';
import { BotSetup } from '@/pages/BotSetup';
import { BotStatus } from '@/pages/BotStatus';
import { TrainingGround } from '@/pages/TrainingGround';
import { Intel } from '@/pages/Intel';
import { Toaster } from '@/components/ui/sonner';
import { useEffect } from 'react';
import { notificationManager } from '@/utils/notifications';
import { notificationPollingService } from '@/utils/notificationPolling';

function App() {
  // Initialize notification system
  useEffect(() => {
    const initNotifications = async () => {
      try {
        await notificationManager.initialize();
        console.log('✅ Notification system initialized');
        
        setTimeout(() => {
          notificationPollingService.startPolling();
        }, 1000);
      } catch (error) {
        console.log('⚠️ Notification system failed to initialize:', error);
      }
    };

    initNotifications();
    
    return () => {
      notificationPollingService.stopPolling();
    };
  }, []);

  return (
    <BrowserRouter>
      <WalletProvider>
        <ScannerProvider>
          <div className="min-h-screen bg-background text-foreground">
            <Navigation />
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/scan" element={<ScannerSetup />} />
              <Route path="/results" element={<ScanResults />} />
              <Route path="/bot" element={<BotSetup />} />
              <Route path="/bot/status" element={<BotStatus />} />
              <Route path="/training" element={<TrainingGround />} />
              <Route path="/intel" element={<Intel />} />
            </Routes>
            <Toaster />
          </div>
        </ScannerProvider>
      </WalletProvider>
    </BrowserRouter>
  );
}

export default App;

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ErrorBoundary } from "react-error-boundary";
import "@github/spark/spark";
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';

import App from './App.tsx';
import { ErrorFallback } from './ErrorFallback.tsx';
import { WalletProvider } from '@/context/WalletContext';
import { ScannerProvider } from '@/context/ScannerContext';

import "./main.css";

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

console.log('[SniperSight] Initializing application...');

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={(error, info) => {
        console.error('[SniperSight] Application error:', error, info);
      }}
    >
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <WalletProvider>
            <ScannerProvider>
              <App />
            </ScannerProvider>
          </WalletProvider>
        </QueryClientProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>
);

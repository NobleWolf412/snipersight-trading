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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <WalletProvider>
          <ScannerProvider>
            <ErrorBoundary FallbackComponent={ErrorFallback}>
              <App />
            </ErrorBoundary>
          </ScannerProvider>
        </WalletProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>
)

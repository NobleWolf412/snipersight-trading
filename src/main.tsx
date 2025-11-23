import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ErrorBoundary } from "react-error-boundary";
import "@github/spark/spark";

import App from './App.tsx';
import { ErrorFallback } from './ErrorFallback.tsx';
import { WalletProvider } from '@/context/WalletContext';
import { ScannerProvider } from '@/context/ScannerContext';

import "./main.css";

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <WalletProvider>
        <ScannerProvider>
          <ErrorBoundary FallbackComponent={ErrorFallback}>
            <App />
          </ErrorBoundary>
        </ScannerProvider>
      </WalletProvider>
    </BrowserRouter>
  </StrictMode>
)

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ErrorBoundary } from "react-error-boundary";

import App from './App.tsx';
import { ErrorFallback } from './ErrorFallback.tsx';
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
        <ScannerProvider>
          <App />
        </ScannerProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>
);

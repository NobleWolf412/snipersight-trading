import type { Meta, StoryObj } from '@storybook/react';
import { BrowserRouter } from 'react-router-dom';
import { ScannerSetup } from './ScannerSetup';
import { ScannerProvider } from '@/context/ScannerContext';
import { WalletProvider } from '@/context/WalletContext';

const meta = {
  title: 'Pages/ScannerSetup',
  component: ScannerSetup,
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <BrowserRouter>
        <WalletProvider>
          <ScannerProvider>
            <Story />
          </ScannerProvider>
        </WalletProvider>
      </BrowserRouter>
    ),
  ],
} satisfies Meta<typeof ScannerSetup>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  play: async () => {
    // Log all interactions to browser console
    window.addEventListener('click', (e) => {
      const target = e.target as HTMLElement;
      if (target.closest('button') || target.closest('[role="button"]')) {
        console.log('[Storybook Action] clicked:', target.textContent?.trim() || target.getAttribute('aria-label') || 'unknown element');
      }
    });
  },
};

export const WithWalletConnected: Story = {
  play: async () => {
    // Mock wallet connection
    localStorage.setItem('wallet-session', JSON.stringify({
      address: '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb',
      provider: 'metamask',
    }));
  },
};

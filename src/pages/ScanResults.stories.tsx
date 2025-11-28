import type { Meta, StoryObj } from '@storybook/react';
import { BrowserRouter } from 'react-router-dom';
import { ScanResults } from './ScanResults';
import { ScannerProvider } from '@/context/ScannerContext';
import { WalletProvider } from '@/context/WalletContext';

const meta = {
  title: 'Pages/ScanResults',
  component: ScanResults,
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
} satisfies Meta<typeof ScanResults>;

export default meta;
type Story = StoryObj<typeof meta>;

// Mock some scan results in localStorage before rendering
const mockScanResults = [
  {
    symbol: 'BTC/USDT',
    direction: 'LONG',
    score: 87.5,
    entry_near: 86500,
    entry_far: 87000,
    stop_loss: 85200,
    targets: [
      { level: 89000, percentage: 50 },
      { level: 91500, percentage: 30 },
      { level: 94000, percentage: 20 },
    ],
    analysis: {
      order_blocks: 5,
      fvgs: 2,
      structural_breaks: 3,
      risk_reward: 2.5,
    },
    conviction_class: 'A' as const,
    plan_type: 'SMC' as const,
    regime: 'ALTSEASON',
    rationale: 'Strong bullish structure with multiple order blocks',
    setup_type: 'OB_FVG_Confluence',
  },
  {
    symbol: 'ETH/USDT',
    direction: 'LONG',
    score: 72.3,
    entry_near: 2850,
    entry_far: 2900,
    stop_loss: 2780,
    targets: [
      { level: 3050, percentage: 50 },
      { level: 3200, percentage: 30 },
      { level: 3400, percentage: 20 },
    ],
    analysis: {
      order_blocks: 3,
      fvgs: 1,
      structural_breaks: 2,
      risk_reward: 1.8,
    },
    conviction_class: 'B' as const,
    plan_type: 'HYBRID' as const,
    regime: 'BTC_DRIVE',
    rationale: 'Decent setup with HTF alignment',
    setup_type: 'Order Block Entry',
  },
];

export const WithResults: Story = {
  play: async () => {
    // Inject mock data into localStorage
    localStorage.setItem('scan-results', JSON.stringify(mockScanResults));
    localStorage.setItem('scan-metadata', JSON.stringify({
      timestamp: new Date().toISOString(),
      mode: 'recon',
      scanned: 10,
      total: 2,
    }));
  },
};

export const NoResults: Story = {
  play: async () => {
    // Clear localStorage
    localStorage.removeItem('scan-results');
    localStorage.removeItem('scan-metadata');
  },
};

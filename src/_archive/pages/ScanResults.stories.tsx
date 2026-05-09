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
    (Story) => {
      // Inject mock data into localStorage before rendering
      localStorage.setItem('scan-results', JSON.stringify(mockScanResults));
      localStorage.setItem('scan-metadata', JSON.stringify({
        timestamp: new Date().toISOString(),
        mode: 'recon',
        scanned: 10,
        total: 2,
      }));
      
      // Mock ticker data for LiveTicker component
      localStorage.setItem('ticker-prices', JSON.stringify({
        'BTC/USDT': { price: 86750, change24h: 2.5 },
        'ETH/USDT': { price: 2875, change24h: 1.8 },
        'SOL/USDT': { price: 145, change24h: -0.5 },
      }));
      
      return (
        <BrowserRouter>
          <WalletProvider>
            <ScannerProvider>
              <Story />
            </ScannerProvider>
          </WalletProvider>
        </BrowserRouter>
      );
    },
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
    confidenceScore: 87.5,
    riskScore: 7.8,
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
    confidenceScore: 72.3,
    riskScore: 6.2,
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

export const WithResults: Story = {};

export const NoResults: Story = {
  decorators: [
    (Story) => {
      // Set up empty results and mock rejectionStats for this story
      localStorage.setItem('scan-results', JSON.stringify([]));
      localStorage.setItem('scan-metadata', JSON.stringify({
        timestamp: new Date().toISOString(),
        mode: 'recon',
        scanned: 10,
        total: 0,
      }));
      localStorage.setItem('scan-rejections', JSON.stringify({
        total_rejected: 10,
        by_reason: {
          'Missing critical timeframe': 4,
          'Low confluence score': 3,
          'No valid trade plan': 2,
          'Risk validation failed': 1,
        },
        details: {
          'BTC/USDT': ['Missing critical timeframe'],
          'ETH/USDT': ['Low confluence score'],
          'SOL/USDT': ['No valid trade plan'],
          'MATIC/USDT': ['Risk validation failed'],
        },
      }));
      return <Story />;
    },
  ],
};

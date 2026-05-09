import type { Meta, StoryObj } from '@storybook/react';
import { PriceCard } from './PriceCard';

const meta = {
  title: 'Components/PriceCard',
  component: PriceCard,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof PriceCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Bitcoin: Story = {
  args: {
    symbol: 'BTC/USDT',
    label: 'Bitcoin',
  },
};

export const Ethereum: Story = {
  args: {
    symbol: 'ETH/USDT',
    label: 'Ethereum',
  },
};

export const Loading: Story = {
  args: {
    symbol: 'SOL/USDT',
    label: 'Solana',
  },
};

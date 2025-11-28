import type { Meta, StoryObj } from '@storybook/react';
import { ConvictionBadge } from './ConvictionBadge';

const meta = {
  title: 'Components/ConvictionBadge',
  component: ConvictionBadge,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    conviction: {
      control: 'select',
      options: ['A', 'B', 'C'],
      description: 'Conviction level of the trading signal',
    },
    planType: {
      control: 'select',
      options: ['SMC', 'ATR_FALLBACK', 'HYBRID'],
      description: 'Type of trade plan',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Badge size',
    },
  },
} satisfies Meta<typeof ConvictionBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const ClassA_SMC: Story = {
  args: {
    conviction: 'A',
    planType: 'SMC',
    size: 'md',
  },
};

export const ClassB_Hybrid: Story = {
  args: {
    conviction: 'B',
    planType: 'HYBRID',
    size: 'md',
  },
};

export const ClassC_ATR: Story = {
  args: {
    conviction: 'C',
    planType: 'ATR_FALLBACK',
    size: 'md',
  },
};

export const Small: Story = {
  args: {
    conviction: 'A',
    planType: 'SMC',
    size: 'sm',
  },
};

export const Large: Story = {
  args: {
    conviction: 'B',
    planType: 'HYBRID',
    size: 'lg',
  },
};

export const WithoutPlanType: Story = {
  args: {
    conviction: 'A',
    planType: 'SMC',
    showPlanType: false,
  },
};

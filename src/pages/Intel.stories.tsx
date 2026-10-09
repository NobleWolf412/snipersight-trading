import type { Meta, StoryObj } from '@storybook/react';
import { BrowserRouter } from 'react-router-dom';
import { Intel } from './Intel';
import { ScannerProvider } from '@/context/ScannerContext';

const meta = {
  title: 'Pages/Intel (Market Overview)',
  component: Intel,
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <BrowserRouter>
        <ScannerProvider>
          <Story />
        </ScannerProvider>
      </BrowserRouter>
    ),
  ],
} satisfies Meta<typeof Intel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

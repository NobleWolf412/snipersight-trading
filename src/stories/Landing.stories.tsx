import type { Meta, StoryObj } from '@storybook/react';
import { Landing } from '@/pages/Landing';
import { MemoryRouter } from 'react-router-dom';
import { WalletProvider } from '@/context/WalletContext';
import { ScannerProvider } from '@/context/ScannerContext';

const meta: Meta<typeof Landing> = {
  title: 'Pages/Landing',
  component: Landing,
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={["/"]}>
        <WalletProvider>
          <ScannerProvider>
            <Story />
          </ScannerProvider>
        </WalletProvider>
      </MemoryRouter>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof Landing>;

export const Default: Story = {
  render: () => <Landing />,
};

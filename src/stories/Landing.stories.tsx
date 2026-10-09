import type { Meta, StoryObj } from '@storybook/react';
import { Landing } from '@/pages/Landing';
import { MemoryRouter } from 'react-router-dom';
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
        <ScannerProvider>
          <Story />
        </ScannerProvider>
      </MemoryRouter>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof Landing>;

export const Default: Story = {
  render: () => <Landing />,
};

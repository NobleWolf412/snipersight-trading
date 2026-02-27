import type { Preview } from '@storybook/react-vite'
import '../src/index.css'

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
       color: /(background|color)$/i,
       date: /Date$/i,
      },
    },
    backgrounds: {
      options: {
        dark: {
          name: 'dark',
          value: '#0a0a0a',
        },

        light: {
          name: 'light',
          value: '#ffffff',
        }
      }
    },
    a11y: {
      config: {
        rules: [
          { id: 'color-contrast', enabled: true },
          { id: 'button-name', enabled: true },
          { id: 'aria-allowed-attr', enabled: true },
        ],
      },
    },
  },

  initialGlobals: {
    backgrounds: {
      value: 'dark'
    }
  }
};

export default preview;
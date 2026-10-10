import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { DEFAULT_SETUP, SetupTab } from './RangeBotViews';

describe('paper setup failure visibility', () => {
  it('keeps a failed start cause beside the final review action', () => {
    const html = renderToStaticMarkup(createElement(SetupTab, {
      sniperMode: 'stealth', cfg: DEFAULT_SETUP, setCfg: vi.fn(),
      onArm: vi.fn(), working: false, armErr: 'Market data unavailable. Retry later.',
    }));
    const review = html.slice(html.indexOf('id="paper-review"'));
    expect(review).toContain('role="alert"');
    expect(review).toContain('Market data unavailable. Retry later.');
    expect(review).toContain('ARM PAPER BOT');
  });
});

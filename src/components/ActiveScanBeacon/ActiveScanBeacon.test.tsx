import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { ActiveScanBeacon } from './ActiveScanBeacon';

const state = vi.hoisted(() => ({
  isScanning: false,
  isBotActive: false,
  isPaperBotActive: false,
  isTrainingActive: false,
}));
vi.mock('@/context/ScannerContext', () => ({ useScanner: () => state }));

function renderAt(route: string) {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[route]}><ActiveScanBeacon /></MemoryRouter>,
  );
}

describe('ActiveScanBeacon session navigation', () => {
  beforeEach(() => {
    Object.assign(state, {
      isScanning: false, isBotActive: false,
      isPaperBotActive: false, isTrainingActive: false,
    });
  });

  it.each(['/', '/scanner', '/bot/status', '/journal', '/intel', '/settings',
    '/training', '/training/range#setup', '/training/range#status', '/training/replay'])
  ('keeps a running paper session reachable from %s', route => {
    state.isPaperBotActive = true;
    const html = renderAt(route);
    expect(html).toContain('href="/training/range#status"');
    expect(html).toContain('aria-label="Paper session running, open status"');
    expect(html).toContain('aria-label="Running tasks"');
  });

  it('does not imply a paper session merely because training is open', () => {
    state.isTrainingActive = true;
    expect(renderAt('/training/range#setup')).toBe('');
  });

  it('renders no beacon when every task is idle', () => {
    expect(renderAt('/')).toBe('');
  });

  it('keeps every simultaneous task directly accessible', () => {
    Object.assign(state, { isScanning: true, isBotActive: true, isPaperBotActive: true });
    const html = renderAt('/settings');
    expect(html).toContain('data-count="3"');
    expect(html).toContain('href="/bot/status"');
    expect(html).toContain('href="/scanner"');
    expect(html).toContain('href="/training/range#status"');
  });

  it.each(['/scanner', '/bot/status'])('preserves owner-page filtering for %s', route => {
    Object.assign(state, { isScanning: true, isBotActive: true, isPaperBotActive: true });
    expect(renderAt(route)).not.toContain(`href="${route}"`);
    expect(renderAt(route)).toContain('href="/training/range#status"');
  });
});

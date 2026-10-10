import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { recommendationIsFresh } from '@/hooks/useScannerRecommendation';

const state = vi.hoisted(() => ({ advice: {} as any, select: vi.fn() }));
vi.mock('@/hooks/useScannerRecommendation', async importOriginal => ({
  ...await importOriginal<typeof import('@/hooks/useScannerRecommendation')>(),
  useScannerRecommendation: () => state.advice,
}));
vi.mock('@/components/hud', () => ({ Chip: ({ children }: any) => children, Reticle: () => null, SectionHead: () => null }));
vi.mock('@/context/ScannerContext', () => ({ useScanner: () => ({
  selectedMode: { name: 'stealth' }, setSelectedMode: state.select,
  scannerModes: ['overwatch', 'strike', 'surgical', 'stealth'].map(name => ({ name,
    timeframes: ['1d', '4h', '15m'], critical_timeframes: ['4h'], primary_planning_timeframe: '15m',
    min_confluence_score: 65, min_rr_ratio: 1.5, description: name })),
}) }));
import { ScannerModePicker } from './ScannerModePicker';
import { BotStrategySettings } from './BotStrategySettings';

beforeEach(() => {
  state.select.mockClear();
  state.advice = { status: 'available', mode: 'strike', reason: '4h trend is clear.', confidence: 'rule_based',
    timestamp: new Date().toISOString(), expires_at: new Date(Date.now() + 120000).toISOString(),
    regime: { composite: 'up_normal' } };
});

describe('authoritative mode advice', () => {
  it('renders backend advice without changing the selected scanner mode', () => {
    const html = renderToStaticMarkup(createElement(ScannerModePicker));
    expect(html).toContain('USE STRIKE');
    expect(html).toContain('4h trend is clear.');
    expect(html).not.toContain('AI ADVISORY');
    expect(state.select).not.toHaveBeenCalled();
  });
  it.each(['stand_aside', 'unavailable'])('does not suggest STEALTH when %s', status => {
    state.advice = { status, mode: null, reason: 'Waiting for usable market evidence.' };
    const html = renderToStaticMarkup(createElement(ScannerModePicker));
    expect(html).toContain('Waiting for usable market evidence.');
    expect(html).not.toContain('USE STEALTH');
    expect(html).not.toContain('RECOMMENDED MODE');
    expect(state.select).not.toHaveBeenCalled();
  });
  it('rejects invalid, future and expired observation times', () => {
    const now = Date.now();
    expect(recommendationIsFresh(state.advice, now)).toBe(true);
    expect(recommendationIsFresh({ ...state.advice, expires_at: new Date(now).toISOString() }, now)).toBe(false);
    expect(recommendationIsFresh({ ...state.advice, timestamp: new Date(now + 1).toISOString() }, now)).toBe(false);
    expect(recommendationIsFresh({ ...state.advice, timestamp: 'bad' }, now)).toBe(false);
  });
  it('keeps requirements in each card rather than a collapsed section', () => {
    const html = renderToStaticMarkup(createElement(ScannerModePicker));
    for (const mode of ['OVERWATCH', 'STRIKE', 'SURGICAL', 'STEALTH']) {
      expect(html).toContain(`${mode} mode requirements`);
      expect(html).toContain(`${mode} mode help`);
    }
    expect(html.match(/Critical data/g)).toHaveLength(4);
    expect(html.match(/Planning TF/g)).toHaveLength(4);
    expect(html.match(/Min R:R/g)).toHaveLength(4);
    expect(html).not.toContain('<details');
  });
  it.each(['expired', 'unknown-mode'])('does not offer stale or unavailable mode application: %s', condition => {
    state.advice = condition === 'expired'
      ? { ...state.advice, expires_at: new Date(Date.now() - 1).toISOString() }
      : { ...state.advice, mode: 'missing-profile' };
    const html = renderToStaticMarkup(createElement(ScannerModePicker));
    expect(html).toContain('Advice unavailable');
    expect(html).toContain('4h trend is clear.');
    expect(html).not.toContain('USE STRIKE');
    expect(html).not.toContain('scanner-mode-card__recommended');
    expect(state.select).not.toHaveBeenCalled();
  });
  it('shows adaptive controls only in paper and retains independent fixed mode for live', () => {
    const config = { sniperMode: 'surgical', selectionMode: 'adaptive', allowedModes: ['strike'] } as any;
    const live = renderToStaticMarkup(createElement(BotStrategySettings, { config, onChange: vi.fn() }));
    const paper = renderToStaticMarkup(createElement(BotStrategySettings, { config, onChange: vi.fn(), paper: true }));
    expect(live).toContain('Bot fixed mode');
    expect(live).not.toContain('Allowed modes');
    expect(paper).toContain('Allowed modes');
    expect(paper).toContain('Adaptive · paper validation');
  });
});

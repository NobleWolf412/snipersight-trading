import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { convertSignalToScanResult } from '@/utils/mockData';
import { passesScoreGate, passesAdmission, admissionLabel } from '@/utils/scoreEvidence';
import type { ScanHistoryEntry } from '@/services/scanHistoryService';

vi.mock('@/components/hud', () => ({ Chip: ({ children }: any) => children, fmtPrice: String }));
vi.mock('@/context/ScannerContext', () => ({ useScanner: () => ({}) }));
vi.mock('@/services/scanHistoryService', () => ({ scanHistoryService: {} }));
import { buildCardSignals, SignalCard } from './Scanner';

function cards(results: any[], gate = 70) {
  return buildCardSignals([{ results, effectiveMinScore: gate } as ScanHistoryEntry]);
}

describe('scanner score evidence', () => {
  it.each(['LONG', 'SHORT'])('preserves %s through backend conversion, history, and rendering', direction => {
    const result = convertSignalToScanResult({ symbol: 'BTCUSDT', direction, score: 73.4,
      entry_far: 99, entry_near: 100, stop_loss: { level: 98 }, targets: [{ level: 105 }],
      confluence_breakdown: { total_score: 73.4, metadata: { score_gate: 72 } },
    });
    const [card] = cards([result]);
    expect(card).toMatchObject({ dir: direction, sym: 'BTC/USDT', score: 73.4, scoreGate: 72 });
    const html = renderToStaticMarkup(createElement(SignalCard, { sig: card }));
    expect(html).toContain('73.4');
    expect(html).toContain('SCORE /100');
    expect(html).not.toMatch(/>HIGH<|>MED<|>LOW<|% confidence/);
  });

  it('keeps identical scores across symbols and display order', () => {
    const results = ['BTC', 'ETH', 'SOL'].map(symbol => ({ symbol, score: 76, direction: 'SHORT' }));
    expect(cards(results).map(c => c.score)).toEqual([76, 76, 76]);
    expect(cards(results.reverse()).map(c => c.score)).toEqual([76, 76, 76]);
  });

  it.each([undefined, null, NaN, Infinity, -1, 101, 'bad'])('shows unavailable for invalid score %s', score => {
    const [card] = cards([{ symbol: 'BTC', direction: 'LONG', score }]);
    expect(card.score).toBeUndefined();
    expect(renderToStaticMarkup(createElement(SignalCard, { sig: card }))).toContain('SCORE UNAVAILABLE');
    expect(passesScoreGate(card.score, 0)).toBe(false);
  });

  it('distinguishes explicit zero from missing score and uses the recorded 0–100 gate', () => {
    const [card] = cards([{ direction: 'LONG', score: 0 }], 0);
    expect(card.score).toBe(0);
    expect(passesScoreGate(card.score, card.scoreGate)).toBe(true);
    expect(passesScoreGate(7, 70)).toBe(false);
    expect(passesScoreGate(69.9, 70)).toBe(false);
    expect(passesScoreGate(70, 70)).toBe(true);
    expect(passesScoreGate(80, undefined)).toBe(false);
  });

  it('does not turn unavailable direction into LONG', () => {
    expect(cards([{ score: 90 }, { score: 90, trendBias: 'NEUTRAL' }])).toEqual([]);
  });

  it.each([undefined, null, NaN, Infinity, -1, 101, 'bad'])('preserves unavailable score %s through conversion and JSON history', score => {
    const converted = convertSignalToScanResult({ symbol: 'BTCUSDT', direction: 'LONG', score,
      entry_far: 99, entry_near: 100, stop_loss: 98, targets: [{ level: 105 }] });
    expect(converted.confidenceScore).toBeUndefined();
    expect(converted.conviction_class).toBeUndefined();
    const [card] = cards([JSON.parse(JSON.stringify(converted))], 0);
    expect(card.score).toBeUndefined();
    expect(passesScoreGate(card.score, card.scoreGate)).toBe(false);
    expect(renderToStaticMarkup(createElement(SignalCard, { sig: card }))).toContain('SCORE UNAVAILABLE');
  });

  it.each([[69.96, 70, true], [69.94, 70, false], [69.96, 70.04, true], [70.25, 70.3, false], [70.75, 70.8, true]])(
    'matches the backend rounded boundary for score %s and gate %s', (score, gate, passed) => {
      const converted = convertSignalToScanResult({ symbol: 'BTCUSDT', direction: 'LONG', score,
        targets: [], confluence_breakdown: { metadata: { score_gate: gate, score_gate_passed: passed } } });
      const [card] = cards([converted]);
      expect(passesScoreGate(card.score, card.scoreGate, card.scoreGatePassed)).toBe(passed);
      expect(passesScoreGate(card.score, card.scoreGate)).toBe(passed);
    });

  it('prefers the recorded result over client reclassification', () => {
    expect(passesScoreGate(80, 70, false)).toBe(false);
    expect(passesScoreGate(undefined, 0, true)).toBe(false);
  });

  it.each(['LONG', 'SHORT'])('keeps numeric pass separate from failed %s evidence through history', direction => {
    const converted = convertSignalToScanResult({ symbol: 'BTCUSDT', direction, score: 85, targets: [],
      confluence_breakdown: { total_score: 85, metadata: {
        score_gate: 70, score_gate_passed: true, evidence_eligible: false, admission_passed: false,
        evidence_missing: ['Confirmed structural shift'], score_model_version: 'family-evidence-v2',
        score_policy_version: 'family-policy-v2',
      } } });
    const [card] = cards([JSON.parse(JSON.stringify(converted))]);
    expect(passesScoreGate(card.score, card.scoreGate, card.scoreGatePassed)).toBe(true);
    expect(passesAdmission(card)).toBe(false);
    expect(card.evidenceMissing).toEqual(['Confirmed structural shift']);
    const html = renderToStaticMarkup(createElement(SignalCard, { sig: card }));
    expect(html).toContain('EVIDENCE REQUIREMENTS NOT MET');
    expect(html).toContain('family-evidence-v2');
    expect(html).not.toContain('ADMISSION PASSED');
  });

  it('uses recorded admission and preserves the historical numeric-only fallback', () => {
    const base = { score: 80, scoreGate: 70, scoreGatePassed: true };
    expect(passesAdmission({ ...base, admissionPassed: false })).toBe(false);
    expect(passesAdmission({ ...base, evidenceEligible: false, admissionPassed: true })).toBe(false);
    expect(passesAdmission({ ...base, scoreGatePassed: false, admissionPassed: true })).toBe(false);
    expect(passesAdmission({ ...base, evidenceEligible: true, admissionPassed: true })).toBe(true);
    expect(admissionLabel({ ...base, evidenceEligible: true, admissionPassed: true })).toBe('ADMISSION PASSED');
    expect(passesAdmission(base)).toBe(true);
    expect(admissionLabel(base)).toBe('SCORE GATE PASSED');
    expect(passesAdmission({ ...base, score: undefined, admissionPassed: true })).toBe(false);
  });

  it.each([undefined, null])('requires explicit v2 eligibility when the recorded value is %s', eligibility => {
    const converted = convertSignalToScanResult({ symbol: 'BTCUSDT', direction: 'LONG', score: 85, targets: [],
      confluence_breakdown: { total_score: 85, metadata: {
        score_model_version: 'family-evidence-v2', score_gate: 70, score_gate_passed: true,
        admission_passed: true, evidence_eligible: eligibility,
      } } });
    const [card] = cards([JSON.parse(JSON.stringify(converted))]);
    expect(card.evidenceEligible).toBeUndefined();
    expect(passesScoreGate(card.score, card.scoreGate, card.scoreGatePassed)).toBe(true);
    expect(passesAdmission(card)).toBe(false);
    expect(admissionLabel(card)).toBe('REQUIRED EVIDENCE UNAVAILABLE');
    expect(passesAdmission({ ...card, admissionPassed: undefined })).toBe(false);
    expect(admissionLabel({ ...card, admissionPassed: undefined })).toBe('REQUIRED EVIDENCE UNAVAILABLE');
    const html = renderToStaticMarkup(createElement(SignalCard, { sig: card }));
    expect(html).toContain('REQUIRED EVIDENCE UNAVAILABLE');
    expect(html).not.toContain('ADMISSION PASSED');
    expect(passesAdmission({ ...card, evidenceEligible: true })).toBe(true);
    expect(passesAdmission({ ...card, scoreModelVersion: undefined })).toBe(true);
  });
});

import { describe, expect, it } from 'vitest';
import { accountingColor, accountingLabel, formatAccountMoney, executionReportNotice, type AccountingStatus } from './accounting';

describe('account valuation display', () => {
  it.each([null, undefined, NaN, Infinity])('shows unavailable %s without a profit color', value => {
    expect(formatAccountMoney(value)).toBe('—');
    expect(accountingColor(value)).toBe('var(--fg-4)');
  });
  it('keeps zero and signed losses distinct from missing evidence', () => {
    expect(formatAccountMoney(0)).toBe('$0.00');
    expect(formatAccountMoney(-125.5)).toBe('-$125.50');
    expect(accountingColor(-125.5)).toBe('var(--red)');
  });
  it.each(['unavailable', 'stale', 'unsupported', 'reconciling'] as const)('labels %s account evidence', state => {
    expect(accountingLabel({ basis: 'exchange_mark', state, entry_eligible: false } as AccountingStatus))
      .toContain(`${state} · new entries paused`);
  });
  it('distinguishes exchange equity from simulation', () => {
    expect(accountingLabel({ basis: 'exchange_mark', state: 'ready', entry_eligible: true } as AccountingStatus))
      .toBe('Exchange account equity · ready');
    expect(accountingLabel({ basis: 'simulation' } as AccountingStatus)).toBe('Simulation equity');
  });
});

describe('execution report completeness', () => {
  it('does not show warnings for simulation or completed reports', () => {
    expect(executionReportNotice()).toBe('');
    expect(executionReportNotice({ entry: { state: 'published' } })).toBe('');
  });
  it('explains that pending trades are excluded without double counting', () => {
    expect(executionReportNotice({ entry: { state: 'pending' } }, {
      reports: [{ entry_order_id: 'entry', state: 'pending' }],
    })).toContain('1 closed trade awaits accounting');
  });
  it('keeps conflicting evidence visible over a formerly published result', () => {
    expect(executionReportNotice({ entry: { state: 'published' } }, {
      reports: [{ entry_order_id: 'entry', state: 'error' }],
    })).toContain('1 trade report needs review');
    expect(executionReportNotice({ entry: { state: 'error' } }, {
      reports: [{ entry_order_id: 'entry', state: 'published' }],
    })).toContain('needs review');
  });
  it('makes a reporting failure visible', () => {
    expect(executionReportNotice({}, { report_error: 'storage unavailable' })).toContain('totals may be incomplete');
  });
});

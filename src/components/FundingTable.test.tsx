import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { FundingTable } from './FundingTable';
import type { FundingRow } from '@/utils/api';

const unavailable: FundingRow = {
  symbol: 'TON/USDT', mark_price: null, price_change_pct: null,
  funding_rate: null, next_funding_ts: null, open_interest: null,
  open_interest_usd: null, error: 'phemex {"error":{"code":6001,"message":"invalid argument"}}',
};
const render = (row: FundingRow) => renderToStaticMarkup(createElement(FundingTable, { rows: [row] }));

describe('funding display availability', () => {
  it('keeps a failed market visible without exposing raw exchange responses', () => {
    const html = render(unavailable);
    expect(html).toContain('TON/USDT');
    expect(html).toContain('Unavailable on Phemex');
    expect(html).not.toMatch(/6001|invalid argument|&quot;error/);
    expect(html).not.toContain('0%');
  });

  it('retains valid price and zero funding when another request fails', () => {
    const html = render({ ...unavailable, mark_price: 0.08503, funding_rate: 0 });
    expect(html).toContain((0.08503).toLocaleString(undefined, { maximumFractionDigits: 8 }));
    expect(html).toContain('>0%<');
    expect(html).toContain('Some data unavailable');
    expect(html).not.toContain('Unavailable on Phemex');
    expect(html).not.toContain('invalid argument');
  });

  it('keeps negative funding and zero open interest distinct from missing data', () => {
    const html = render({ ...unavailable, error: null, funding_rate: -0.000052, open_interest_usd: 0 });
    expect(html).toContain(`${(-0.0052).toLocaleString(undefined, { maximumFractionDigits: 6 })}%`);
    expect(html).toContain('>0<');
    expect(html).not.toContain('Some data unavailable');
  });

  it('does not display invalid numeric values or an invented settlement time', () => {
    const html = render({ ...unavailable, error: null, mark_price: NaN, funding_rate: Infinity,
      open_interest_usd: -Infinity, next_funding_ts: 'invalid' });
    expect(html).toContain('Unavailable on Phemex');
    expect(html).not.toMatch(/NaN|Infinity|Invalid Date/);
  });
});

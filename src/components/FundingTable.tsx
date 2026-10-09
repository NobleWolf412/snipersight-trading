import type { FundingRow } from '@/utils/api';
import './FundingTable.css';

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const number = (value: unknown, digits: number) => finite(value)
  ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : 'Unavailable';

export function FundingTable({ rows }: { rows: FundingRow[] }) {
  if (!rows.length) return <p>No funding markets returned.</p>;
  return <table className="funding-table" role="table" aria-label="Phemex funding and open interest">
    <thead role="rowgroup"><tr role="row">
      <th scope="col" role="columnheader">Pair</th>
      <th scope="col" role="columnheader">Price (USDT)</th>
      <th scope="col" role="columnheader">Funding rate</th>
      <th scope="col" role="columnheader">Open interest (USD)</th>
      <th scope="col" role="columnheader">Next funding</th>
    </tr></thead>
    <tbody role="rowgroup">{rows.map(row => {
      const nextFunding = row.next_funding_ts && Number.isFinite(Date.parse(row.next_funding_ts))
        ? new Date(row.next_funding_ts).toLocaleString() : 'Unavailable';
      const hasData = [row.mark_price, row.funding_rate, row.open_interest_usd].some(finite)
        || nextFunding !== 'Unavailable';
      return <tr key={row.symbol} role="row">
        <th scope="row" role="rowheader">
          {row.symbol}
          {(!hasData || row.error) && <span className="funding-table__status">
            {hasData ? 'Some data unavailable' : 'Unavailable on Phemex'}
          </span>}
        </th>
        {[
          ['Price (USDT)', number(row.mark_price, 8)],
          ['Funding rate', finite(row.funding_rate) ? `${number(row.funding_rate * 100, 6)}%` : 'Unavailable'],
          ['Open interest (USD)', number(row.open_interest_usd, 2)],
          ['Next funding', nextFunding],
        ].map(([label, value]) => <td key={label} role="cell">
          <span className="funding-table__label" aria-hidden="true">{label}</span>
          <span className={value === 'Unavailable' ? 'funding-table__missing' : undefined}>{value}</span>
        </td>)}
      </tr>;
    })}</tbody>
  </table>;
}

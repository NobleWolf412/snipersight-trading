import { type ReactNode } from 'react';
import { useFreshFeed } from '@/hooks/useFreshFeed';
import { observationDeadline } from '@/services/freshFeed';
import { Link } from 'react-router-dom';
import { PageHead, SectionHead, Chip } from '@/components/hud';
import { api, type FundingResponse, type FearGreedResponse, type TradFiResponse, type BTCCycleContextData } from '@/utils/api';
import { useMarketRegime } from '@/hooks/useMarketRegime';

const number = (value: unknown, digits = 2) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
const time = (value?: string | null) => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Unavailable';
function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="panel"><SectionHead title={title} /><div style={{ padding: 20, overflowX: 'auto' }}>{children}</div></section>;
}
export function Intel() {
  const regime = useMarketRegime();
  const fundingFeed = useFreshFeed(() => api.getFundingRates(), (value, now) =>
    Math.min(now + 90000, observationDeadline(value.cached_at, 300000, now)));
  const sentimentFeed = useFreshFeed(() => api.getFearGreed(), (value, now) =>
    value.source === 'alternative.me' && Number.isFinite(value.value) && value.value >= 0 && value.value <= 100
      ? Math.min(now + 90000, observationDeadline(value.timestamp, 36 * 3600000, now)) : NaN);
  const tradfiFeed = useFreshFeed(() => api.getTradFi(), (value, now) =>
    value.source !== 'fallback' ? Math.min(now + 90000, observationDeadline(value.cached_at, 300000, now)) : NaN);
  const funding = fundingFeed.data, sentiment = sentimentFeed.data, tradfi = tradfiFeed.data;
  const loading = fundingFeed.loading || sentimentFeed.loading || tradfiFeed.loading;
  const errors = [fundingFeed.error, sentimentFeed.error, tradfiFeed.error].filter(Boolean);
  const receivedAt = [fundingFeed.receivedAt, sentimentFeed.receivedAt, tradfiFeed.receivedAt].filter(Boolean).sort().reverse()[0];
  const refresh = () => { regime.retry(); void fundingFeed.retry(); void sentimentFeed.retry(); void tradfiFeed.retry(); };
  return <div className="page">
    <PageHead title="Market Intel" subtitle="Observed market context · sources and freshness shown below" icon={<span>◎</span>}
      badges={<Chip>{regime.regimeLabel}</Chip>} />
    <div style={{ display: 'flex', gap: 16, alignItems: 'center', margin: '16px 0', flexWrap: 'wrap' }}>
      <button className="btn btn-cyan" disabled={loading || regime.loading} onClick={refresh}>{loading || regime.loading ? 'Refreshing…' : 'Refresh feeds'}</button>
      <span>Last response: {time(receivedAt)}</span><Link to="/scanner">Open scanner and mode recommendation</Link>
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 390px), 1fr))', gap: 18 }}>
      <Panel title="Global regime">
        {regime.error && <p role="status">{regime.error}</p>}
        <p><strong>{regime.regimeLabel}</strong> · score {number(regime.compositeScore, 1)} / 100</p>
        <p>Analyzed {time(regime.observedAt)} · valid until {time(regime.expiresAt)}</p>
        <dl>{[['Trend', regime.trendScore], ['Volatility', regime.volatilityScore], ['Liquidity', regime.liquidityScore], ['Risk appetite', regime.riskScore], ['Derivatives', regime.derivativesScore]].map(([label, score]) => <div key={String(label)} style={{ display: 'flex', justifyContent: 'space-between', margin: '10px 0' }}><dt>{label}</dt><dd>{number(score, 1)}</dd></div>)}</dl>
        <p>These are heuristic context scores, not probabilities or trade eligibility. Each scan applies its own mode rules.</p>
      </Panel>
      <Panel title="Global market capitalization shares">
        <p>BTC: <strong>{number(regime.btcDominance)}%</strong></p>
        <p>USDT + USDC: <strong>{number(regime.usdtDominance)}%</strong></p>
        <p>Remaining market: <strong>{number(regime.altDominance)}%</strong></p>
        <p>{regime.dominanceSource ?? 'Source unavailable'}</p>
        <p>Provider observation: {time(regime.dominanceObservedAt)}</p>
        <p>Remaining includes other stablecoins. Shares describe capitalization, not capital flows.</p>
      </Panel>
      <Panel title="Market sentiment">
        <p>Fear &amp; Greed: <strong>{sentiment ? `${sentiment.value}/100 · ${sentiment.classification}` : 'Unavailable'}</strong></p>
        <p>Alternative.me observation: {time(sentiment?.timestamp)}</p>
        <p>Sentiment is context, not the bot’s entry veto.</p>
      </Panel>
      <Panel title="Traditional markets">
        {!tradfi && <p>Quotes unavailable.</p>}
        {tradfi?.rows.map(row => <div key={row.key} style={{ marginBottom: 14 }}><strong>{row.label}: {row.error ? 'Unavailable' : number(row.value)} {row.currency}</strong><div>As of {time(row.as_of)} · {row.error ?? `${number(row.delta_pct)}% vs previous close`}</div></div>)}
        {tradfi && <p>Source: {tradfi.source}. Closed-market quotes retain their observation time.</p>}
      </Panel>
    </div>
    <div style={{ marginTop: 18 }}><Panel title="Funding and open interest · Phemex">
      {!funding && <p>Funding feed unavailable. No substitute values are shown.</p>}
      {funding && <><p>Received by backend: {time(funding.cached_at)}</p><table style={{ width: '100%', textAlign: 'left' }}><thead><tr><th>Pair</th><th>Mark</th><th>Funding</th><th>Open interest USD</th><th>Next funding</th></tr></thead><tbody>
        {funding.rows.map(row => <tr key={row.symbol}><td>{row.symbol}{row.error && <div>{row.error}</div>}</td><td>{row.error ? '—' : number(row.mark_price)}</td><td>{row.error || row.funding_rate == null ? '—' : `${number(row.funding_rate * 100, 4)}%`}</td><td>{row.error ? '—' : number(row.open_interest_usd)}</td><td>{time(row.next_funding_ts)}</td></tr>)}
      </tbody></table></>}
    </Panel></div>
    {errors.length > 0 && <p role="status">{errors.join(' ')}</p>}
  </div>;
}

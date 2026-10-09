import { useMarketRegime } from '@/hooks/useMarketRegime';
export function MacroScoreTile() {
  const regime = useMarketRegime();
  const score = regime.compositeScore;
  return <div className="metric-tile">
    <div className="metric-label">Macro Score</div>
    <div className="metric-value">{score === undefined ? '—' : score.toFixed(1)}</div>
    <div className="metric-sub">{regime.regimeLabel}</div>
    <button className="btn" disabled={regime.loading} onClick={regime.retry}>Refresh</button>
    {regime.error && <div role="status">{regime.error}</div>}
    {regime.observedAt && <small>Analyzed {new Date(regime.observedAt).toLocaleTimeString()}</small>}
  </div>;
}

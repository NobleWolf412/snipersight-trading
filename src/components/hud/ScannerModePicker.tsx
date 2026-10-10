import type { CSSProperties } from 'react';
import { Reticle } from '@/components/hud/Reticle';
import { useScanner } from '@/context/ScannerContext';
import { recommendationIsFresh,useScannerRecommendation } from '@/hooks/useScannerRecommendation';

export function ScannerModePicker() {
  const { scannerModes, selectedMode, setSelectedMode } = useScanner();
  const rec = useScannerRecommendation();
  const recMode = scannerModes.find(mode => mode.name === rec.mode);
  const usable = rec.status === 'available' && !!recMode && recommendationIsFresh(rec);
  const select = (name: string) => {
    const mode = scannerModes.find(item => item.name === name);
    if (mode) setSelectedMode(mode);
  };
  return <div className="scanner-mode-summary">
    <div className="scanner-mode-cards" role="group" aria-label="Choose scanner mode">
      {scannerModes.map(mode => {
        const color = ({ overwatch: 'var(--cyan)', strike: 'var(--amber)', surgical: 'var(--red-2)', stealth: 'var(--green-soft)' } as Record<string, string>)[mode.name] ?? 'var(--accent)';
        const active = selectedMode?.name === mode.name;
        return <button type="button" key={mode.name} className="scanner-mode-card"
          aria-pressed={active} aria-label={`Select ${mode.name.toUpperCase()} mode`}
          style={{ '--mode-accent': color } as CSSProperties} onClick={() => select(mode.name)}>
          <span className="scanner-mode-card__art" aria-hidden="true"><Reticle /></span>
          <span className="scanner-mode-card__name">{mode.name.toUpperCase()}</span>
          <span className="scanner-mode-card__timeframes mono">{mode.timeframes.join(' · ')}</span>
          <span className="scanner-mode-card__limits mono">Score: {mode.min_confluence_score != null ? `≥ ${mode.min_confluence_score}` : 'Unavailable'} · R:R: {mode.min_rr_ratio ?? 'Unavailable'}</span>
          <span className="scanner-mode-card__state mono">{active ? 'SELECTED' : 'SELECT MODE'}</span>
        </button>;
      })}
    </div>
    <label className="scanner-mode-select">Scanner mode
      <select value={selectedMode?.name ?? ''} disabled={!scannerModes.length}
        onChange={event => select(event.target.value)}>
        {!selectedMode && <option value="">Mode definitions unavailable</option>}
        {scannerModes.map(mode => <option key={mode.name} value={mode.name}>{mode.name.toUpperCase()}</option>)}
      </select>
    </label>
    <div>
      <p className="mono">Timeframes: {selectedMode?.timeframes?.join(' · ') || 'Unavailable'}</p>
      <p>Critical data: {selectedMode?.critical_timeframes?.join(' · ') || 'See mode requirements'}</p>
    </div>
    <details>
      <summary>Mode requirements and advice</summary>
      <p>{selectedMode?.description || 'Reload mode definitions in Scan inputs.'}</p>
      <p>Mode default score: {selectedMode?.min_confluence_score ?? 'Unavailable'}.
        Minimum R:R: {selectedMode?.min_rr_ratio ?? 'Unavailable'}.
        Planning timeframe: {selectedMode?.primary_planning_timeframe ?? 'Unavailable'}.</p>
      <p>Mode advice is a hypothesis, not a win probability. Scanner selection stays manual.</p>
    </details>
    <div className="scanner-mode-advice">
      <p>{rec.status === 'stand_aside' ? 'Stand aside: ' : usable ? 'Mode advice: ' : 'Advice unavailable: '}
        {rec.reason}</p>
      {rec.warning && <p>{rec.warning}</p>}
      {usable && selectedMode?.name !== recMode.name &&
        <button className="btn" onClick={() => select(recMode.name)}>USE {recMode.name.toUpperCase()}</button>}
    </div>
  </div>;
}
export default ScannerModePicker;

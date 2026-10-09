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
    <label>Scanner mode
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

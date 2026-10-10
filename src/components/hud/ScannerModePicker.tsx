import { useState, type CSSProperties, type ReactNode } from 'react';
import { Reticle } from '@/components/hud/Reticle';
import { Modal } from '@/components/hud/Modal';
import { useScanner } from '@/context/ScannerContext';
import { recommendationIsFresh, useScannerRecommendation } from '@/hooks/useScannerRecommendation';
import type { ScannerMode } from '@/utils/api';

const colors: Record<string, string> = {
  overwatch: 'var(--cyan)', strike: 'var(--amber)',
  surgical: 'var(--red-2)', stealth: 'var(--green-soft)',
};
const modeColor = (name: string) => colors[name] ?? 'var(--accent)';
const timeframes = (values?: string[]) => values?.length ? values.join(' · ') : 'Unavailable';

function HelpIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
    <path d="M12 11v6M12 7v1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>;
}

function ModeCard({ mode, selected, recommended, onSelect, onHelp }: {
  mode: ScannerMode; selected: boolean; recommended: boolean;
  onSelect: () => void; onHelp: () => void;
}) {
  return <article className="scanner-mode-card" data-selected={selected}
    aria-label={`${mode.name.toUpperCase()} mode requirements`}
    style={{ '--mode-accent': modeColor(mode.name) } as CSSProperties}>
    <span className="scanner-mode-card__art" aria-hidden="true"><Reticle /></span>
    <header className="scanner-mode-card__header">
      <h3 className="scanner-mode-card__name">{mode.name.toUpperCase()}</h3>
      <button type="button" className="btn btn-icon scanner-help-button"
        aria-label={`${mode.name.toUpperCase()} mode help`} aria-haspopup="dialog" onClick={onHelp}><HelpIcon /></button>
    </header>
    {recommended && <span className="scanner-mode-card__recommended mono">RECOMMENDED</span>}
    <dl className="scanner-mode-card__metrics">
      <div><dt>Min score</dt><dd>{mode.min_confluence_score ?? 'Unavailable'}</dd></div>
      <div><dt>Min R:R</dt><dd>{mode.min_rr_ratio ?? 'Unavailable'}</dd></div>
      <div><dt>Planning TF</dt><dd>{mode.primary_planning_timeframe ?? 'Unavailable'}</dd></div>
    </dl>
    <div className="scanner-mode-card__requirements">
      <p className="scanner-mode-card__label">Critical data <span>(reject if missing)</span></p>
      <p className="mono scanner-mode-card__critical">{timeframes(mode.critical_timeframes)}</p>
      <p className="scanner-mode-card__label">Analysis timeframes</p>
      <p className="mono">{timeframes(mode.timeframes)}</p>
    </div>
    <button type="button" className="btn scanner-mode-card__select" aria-pressed={selected}
      aria-label={`Select ${mode.name.toUpperCase()} mode`} onClick={onSelect}>
      {selected ? 'SELECTED' : 'SELECT MODE'}
    </button>
  </article>;
}

export function ScannerModePicker({ actions }: { actions?: ReactNode }) {
  const { scannerModes, selectedMode, setSelectedMode } = useScanner();
  const rec = useScannerRecommendation();
  const [help, setHelp] = useState<string | null>(null);
  const [adviceHelp, setAdviceHelp] = useState(false);
  const helpMode = scannerModes.find(mode => mode.name === help);
  const recMode = scannerModes.find(mode => mode.name === rec.mode);
  const usable = rec.status === 'available' && !!recMode && recommendationIsFresh(rec);
  const standAside = rec.status === 'stand_aside' && recommendationIsFresh(rec);
  const color = usable ? modeColor(recMode.name) : standAside ? 'var(--amber)' : 'var(--fg-2)';
  const select = (name: string) => {
    const mode = scannerModes.find(item => item.name === name);
    if (mode) setSelectedMode(mode);
  };
  const unavailableCause = rec.status !== 'unavailable' && !usable && !standAside
    ? !recommendationIsFresh(rec) ? 'Market analysis has expired.' : 'Recommended mode definitions are unavailable.'
    : null;

  return <div className="scanner-mode-summary">
    <section className="scanner-recommendation" aria-label="Scanner mode recommendation"
      style={{ '--mode-accent': color } as CSSProperties}>
      <div className="scanner-recommendation__content">
        <div className="scanner-recommendation__eyebrow mono">
          <span>MARKET GUIDANCE</span>
          {rec.regime?.composite && <span className="chip">{rec.regime.composite.toUpperCase()}</span>}
        </div>
        <h2>{usable ? 'Recommended mode' : standAside ? 'Stand aside' : 'Advice unavailable'}</h2>
        {usable && <div className="scanner-recommendation__mode">{recMode.name.toUpperCase()}</div>}
        <p>{rec.reason}</p>
        {unavailableCause && <p className="scanner-recommendation__warning">{unavailableCause}</p>}
        {rec.warning && <p className="scanner-recommendation__warning">{rec.warning}</p>}
        <p className="scanner-recommendation__note">Mode advice is a hypothesis, not a win probability. Selection stays manual.</p>
      </div>
      <div className="scanner-recommendation__actions">
        <button type="button" className="btn btn-icon scanner-help-button" aria-label="Mode recommendation help"
          aria-haspopup="dialog" onClick={() => setAdviceHelp(true)}><HelpIcon /></button>
        {usable && (selectedMode?.name === recMode.name
          ? <span className="scanner-recommendation__selected mono">SELECTED</span>
          : <button type="button" className="btn btn-green" onClick={() => {
            if (recommendationIsFresh(rec)) select(recMode.name);
          }}>USE {recMode.name.toUpperCase()}</button>)}
      </div>
    </section>
    {actions && <div className="scanner-primary-actions">{actions}</div>}
    <div className="scanner-mode-heading">
      <h2>Detection modes</h2>
      <span className="mono">{selectedMode ? `SELECTED: ${selectedMode.name.toUpperCase()}` : 'CHOOSE A MODE'}</span>
    </div>
    <div className="scanner-mode-cards" role="group" aria-label="Choose scanner mode">
      {scannerModes.map(mode => <ModeCard key={mode.name} mode={mode}
        selected={selectedMode?.name === mode.name} recommended={usable && recMode.name === mode.name}
        onSelect={() => select(mode.name)} onHelp={() => setHelp(mode.name)} />)}
      {!scannerModes.length && <p>Mode definitions unavailable. Reload definitions in Scan inputs.</p>}
    </div>
    {helpMode && <Modal label={`${helpMode.name.toUpperCase()} mode help`} onClose={() => setHelp(null)}>
      <div className="scanner-help-content">
        <h2>{helpMode.name.toUpperCase()}</h2>
        <p>{helpMode.description || 'Mode description unavailable.'}</p>
        <p>Card requirements are mode defaults. Missing critical data rejects a setup before its score is accepted. A score is evidence credit, not a win probability.</p>
        <dl className="scanner-help-ledger">
          <div><dt>Profile</dt><dd>{helpMode.profile || 'Unavailable'}</dd></div>
          <div><dt>Entry timeframes</dt><dd>{timeframes(helpMode.entry_timeframes)}</dd></div>
          <div><dt>Structure timeframes</dt><dd>{timeframes(helpMode.structure_timeframes)}</dd></div>
          <div><dt>Zone timeframes</dt><dd>{timeframes(helpMode.zone_timeframes)}</dd></div>
          <div><dt>Stop timeframes</dt><dd>{timeframes(helpMode.stop_timeframes)}</dd></div>
          <div><dt>Target timeframes</dt><dd>{timeframes(helpMode.target_timeframes)}</dd></div>
          <div><dt>ATR multiplier</dt><dd>{helpMode.atr_multiplier ?? 'Unavailable'}</dd></div>
        </dl>
      </div>
    </Modal>}
    {adviceHelp && <Modal label="Mode recommendation help" onClose={() => setAdviceHelp(false)}>
      <div className="scanner-help-content">
        <h2>Mode recommendation</h2>
        <p>Market context suggests a mode to inspect. It never selects a mode or starts a scan. Each setup still needs its own evidence and risk checks.</p>
        <dl className="scanner-help-ledger">
          <div><dt>State</dt><dd>{usable ? 'Available' : standAside ? 'Stand aside' : 'Unavailable'}</dd></div>
          <div><dt>Observed</dt><dd>{rec.timestamp || 'Unavailable'}</dd></div>
          <div><dt>Expires</dt><dd>{rec.expires_at || 'Unavailable'}</dd></div>
          <div><dt>Reference timeframe</dt><dd>{rec.reference_timeframe || 'Unavailable'}</dd></div>
          <div><dt>Policy</dt><dd>{rec.policy_version || 'Unavailable'}</dd></div>
        </dl>
      </div>
    </Modal>}
  </div>;
}
export default ScannerModePicker;

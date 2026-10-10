import { useScanner, defaultScanConfig } from '@/context/ScannerContext';
import { scanRunService, scanIsBusy } from '@/services/scanRunService';
import { useState, useSyncExternalStore } from 'react';
import { Modal } from '@/components/hud/Modal';

export function ScannerInputs() {
  const { scanConfig: config, setScanConfig, refreshModes } = useScanner();
  const progress = useSyncExternalStore(scanRunService.subscribe, scanRunService.getSnapshot);
  const [macroHelpOpen, setMacroHelpOpen] = useState(false);
  const set = <K extends keyof typeof config>(field: K, value: typeof config[K]) => setScanConfig({ ...config, [field]: value });
  return <section className="scanner-inputs" aria-label="Scan inputs">
    <h2>Scan inputs</h2>
    <fieldset disabled={scanIsBusy(progress.status)}>
      <div className="scanner-inputs__fields">
        <label>Exchange <select value={config.exchange.toLowerCase()} onChange={e => set('exchange', e.target.value)}>{['phemex', 'binance', 'bybit'].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Pairs <input type="number" min={1} max={100} value={config.topPairs} onChange={e => set('topPairs', Math.max(1, Math.min(100, Number(e.target.value) || 1)))} /></label>
        <label>Target pair (optional) <input value={config.targetSymbol ?? ''} placeholder="BTC/USDT" onChange={e => set('targetSymbol', e.target.value.trim().toUpperCase())} /></label>
        <label>Market <select value={config.marketType ?? 'swap'} onChange={e => set('marketType', e.target.value)}><option value="swap">Perpetual</option><option value="spot">Spot</option></select></label>
        <label>Leverage <input type="number" min={1} max={125} value={config.leverage} onChange={e => set('leverage', Math.max(1, Math.min(125, Number(e.target.value) || 1)))} /></label>
      </div>
      <div className="scanner-inputs__toggles">
        {(['majors', 'altcoins', 'memeMode'] as const).map(key => <label key={key}><input type="checkbox" checked={config.categories[key]} onChange={e => set('categories', { ...config.categories, [key]: e.target.checked })} /> {key === 'memeMode' ? 'Meme coins' : key === 'majors' ? 'Majors' : 'Altcoins'}</label>)}
        <div className="scanner-inputs__macro">
          <label><input type="checkbox" checked={config.macroOverlay} onChange={e => set('macroOverlay', e.target.checked)} /> Macro overlay</label>
          <button type="button" className="btn btn-icon scanner-help-button" aria-label="Macro overlay help" aria-haspopup="dialog" onClick={() => setMacroHelpOpen(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
              <path d="M12 11v6M12 7v1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>
      <div className="scanner-inputs__footer">
        <p>Inputs apply to the next scan. Timeframes and score policy come from the selected mode.</p>
        <button type="button" className="btn" onClick={() => setScanConfig({ ...defaultScanConfig, sniperMode: config.sniperMode })}>Reset scan inputs</button>
        <button type="button" className="btn" onClick={() => void refreshModes()}>Reload mode definitions</button>
      </div>
    </fieldset>
    {macroHelpOpen && <Modal label="Macro overlay help" onClose={() => setMacroHelpOpen(false)} maxWidth={520}>
      <div className="scanner-help-content">
        <h2>Macro overlay</h2>
        <p>Adds the wider crypto market to setup scoring: Bitcoin, altcoin and stablecoin dominance, market direction and how broadly coins are participating.</p>
        <p>This context can strengthen or reduce the setup's contextual evidence within the existing score limits. If required market context is unavailable, an enabled overlay rejects the setup with a reason.</p>
        <p>Applies to the next scan. Turning it off skips this overlay; the selected mode's requirements and other safety checks still apply.</p>
      </div>
    </Modal>}
  </section>;
}

import { useScanner, defaultScanConfig } from '@/context/ScannerContext';
import { scanRunService, scanIsBusy } from '@/services/scanRunService';
import { useSyncExternalStore } from 'react';

export function ScannerInputs() {
  const { scanConfig: config, setScanConfig, refreshModes } = useScanner();
  const progress = useSyncExternalStore(scanRunService.subscribe, scanRunService.getSnapshot);
  const set = <K extends keyof typeof config>(field: K, value: typeof config[K]) => setScanConfig({ ...config, [field]: value });
  return <details style={{ margin: '14px 0' }}>
    <summary>Scan inputs · {config.exchange} · {config.targetSymbol ? `TARGET: ${config.targetSymbol}` : `up to ${config.topPairs} pairs`} · {config.marketType ?? 'swap'} · {config.leverage}× {config.macroOverlay ? '· macro overlay on' : ''}</summary>
    <fieldset disabled={scanIsBusy(progress.status)} style={{ display: 'flex', gap: 14, flexWrap: 'wrap', padding: 16 }}>
      <label>Exchange <select value={config.exchange.toLowerCase()} onChange={e => set('exchange', e.target.value)}>{['phemex', 'binance', 'bybit'].map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Pairs <input type="number" min={1} max={100} value={config.topPairs} onChange={e => set('topPairs', Math.max(1, Math.min(100, Number(e.target.value) || 1)))} /></label>
      <label>Target pair (optional) <input value={config.targetSymbol ?? ''} placeholder="BTC/USDT" onChange={e => set('targetSymbol', e.target.value.trim().toUpperCase())} /></label>
      <label>Leverage <input type="number" min={1} max={125} value={config.leverage} onChange={e => set('leverage', Math.max(1, Math.min(125, Number(e.target.value) || 1)))} /></label>
      <label>Market <select value={config.marketType ?? 'swap'} onChange={e => set('marketType', e.target.value)}><option value="swap">Perpetual</option><option value="spot">Spot</option></select></label>
      {(['majors', 'altcoins', 'memeMode'] as const).map(key => <label key={key}><input type="checkbox" checked={config.categories[key]} onChange={e => set('categories', { ...config.categories, [key]: e.target.checked })} /> {key}</label>)}
      <label><input type="checkbox" checked={config.macroOverlay} onChange={e => set('macroOverlay', e.target.checked)} /> Macro overlay</label>
      <button className="btn" onClick={() => setScanConfig({ ...defaultScanConfig, sniperMode: config.sniperMode })}>Reset scan inputs</button>
      <button className="btn" onClick={() => void refreshModes()}>Reload mode definitions</button>
    </fieldset>
    <p>Inputs apply to the next scan. Timeframes and score policy come from the selected mode.</p>
  </details>;
}

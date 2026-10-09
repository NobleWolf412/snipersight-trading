import type { BotConfig } from '@/context/ScannerContext';
import type { SniperMode } from '@/types/sniperMode';

const modes: SniperMode[] = ['overwatch', 'strike', 'surgical', 'stealth'];

export function BotStrategySettings({ config, onChange, paper = false }: {
  config: BotConfig; onChange: (config: BotConfig) => void; paper?: boolean;
}) {
  const adaptive = paper && config.selectionMode === 'adaptive';
  const allowed = config.allowedModes ?? ['strike', 'surgical', 'stealth'];
  return <section className="panel" style={{ padding: 18, marginBottom: 14 }}>
    <strong>Bot strategy</strong>
    <p style={{ color: 'var(--fg-3)' }}>Choose how this bot finds setups. Scanner choices stay separate.</p>
    {paper && <label style={{ display: 'block', marginBottom: 12 }}>Selection{' '}
      <select aria-label="Bot strategy selection" value={adaptive ? 'adaptive' : 'fixed'}
        onChange={event => onChange({ ...config, selectionMode: event.target.value as 'fixed' | 'adaptive' })}>
        <option value="fixed">Fixed mode</option><option value="adaptive">Adaptive · paper validation</option>
      </select>
    </label>}
    {adaptive ? <fieldset><legend>Allowed modes</legend>
      {modes.map(mode => <label key={mode} style={{ marginRight: 16 }}>
        <input type="checkbox" checked={allowed.includes(mode)}
          disabled={allowed.length === 1 && allowed.includes(mode)}
          onChange={event => onChange({ ...config, allowedModes: event.target.checked
            ? [...allowed, mode] : allowed.filter(item => item !== mode) })} /> {mode.toUpperCase()}
      </label>)}
      <p>The bot waits when no permitted mode fits or market data is unavailable. Existing trades keep their original plan.</p>
    </fieldset> : <label>Fixed mode{' '}
      <select aria-label="Bot fixed mode" value={config.sniperMode ?? 'stealth'}
        onChange={event => onChange({ ...config, sniperMode: event.target.value as SniperMode })}>
        {modes.map(mode => <option key={mode} value={mode}>{mode.toUpperCase()}</option>)}
      </select>
    </label>}
    {!paper && <p style={{ color: 'var(--fg-3)' }}>Live trading uses a fixed mode. Adaptive selection is available in paper trading.</p>}
    <p style={{ color: 'var(--fg-3)' }}>The selected mode sets the minimum setup score. Bot thresholds can raise that minimum.</p>
  </section>;
}

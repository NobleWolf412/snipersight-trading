import type { BotConfig } from '@/context/ScannerContext';
import type { SniperMode } from '@/types/sniperMode';
import { DialogPanel } from './DialogPanel';

const modes: SniperMode[] = ['overwatch', 'strike', 'surgical', 'stealth'];

export function BotStrategySettings({ config, onChange, paper = false }: {
  config: BotConfig; onChange: (config: BotConfig) => void; paper?: boolean;
}) {
  const adaptive = paper && config.selectionMode === 'adaptive';
  const allowed = config.allowedModes ?? ['strike', 'surgical', 'stealth'];
  return <section id={paper ? 'paper-strategy' : undefined} className="panel bot-strategy-settings" aria-label="Bot strategy">
    <header className="setup-section-heading"><h2>{paper ? '01 · Choose strategy' : 'Bot strategy'}</h2>
      <DialogPanel label="Bot strategy help" icon maxWidth={560}>
        <p>Fixed mode keeps the selected playbook for the whole session. Scanner choices stay separate.</p>
        <p>Adaptive selection is for paper validation. It chooses from the permitted modes using market advice and waits when no permitted mode fits or data is unavailable. Existing trades keep their original plan.</p>
        <p>The mode sets the minimum setup score. Bot thresholds can raise that minimum. Scores are evidence credit, not win probabilities.</p>
      </DialogPanel>
    </header>
    {paper && <div className="setup-choice-row" role="group" aria-label="Bot strategy selection">
      {(['fixed', 'adaptive'] as const).map(selection => <button key={selection} type="button"
        className={`btn ${adaptive === (selection === 'adaptive') ? 'btn-cyan' : ''}`}
        aria-pressed={adaptive === (selection === 'adaptive')}
        onClick={() => onChange({ ...config, selectionMode: selection })}>
        {selection === 'fixed' ? 'Fixed mode' : 'Adaptive · paper validation'}
      </button>)}
    </div>}
    {adaptive ? <fieldset><legend>Allowed modes</legend>
      {modes.map(mode => <label key={mode} style={{ marginRight: 16 }}>
        <input type="checkbox" checked={allowed.includes(mode)}
          disabled={allowed.length === 1 && allowed.includes(mode)}
          onChange={event => onChange({ ...config, allowedModes: event.target.checked
            ? [...allowed, mode] : allowed.filter(item => item !== mode) })} /> {mode.toUpperCase()}
      </label>)}
      <p>The bot waits when no permitted mode fits or market data is unavailable. Existing trades keep their original plan.</p>
    </fieldset> : <div className="setup-choice-row" role="group" aria-label="Bot fixed mode">
      {modes.map(mode => <button key={mode} type="button" aria-pressed={(config.sniperMode ?? 'stealth') === mode}
        className={`btn ${(config.sniperMode ?? 'stealth') === mode ? 'btn-cyan' : ''}`}
        onClick={() => onChange({ ...config, sniperMode: mode })}>{mode.toUpperCase()}</button>)}
    </div>}
    {!paper && <p style={{ color: 'var(--fg-3)' }}>Live trading uses a fixed mode. Adaptive selection is available in paper trading.</p>}
    <p className="setup-note">{adaptive ? 'Select permitted modes. Existing trades keep their original plan.' : 'Selected mode applies to the next bot session.'}</p>
  </section>;
}

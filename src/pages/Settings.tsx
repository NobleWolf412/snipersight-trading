import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHead, SectionHead, Chip } from '@/components/hud';
import { useBrowserPreferences, saveBrowserPreferences } from '@/services/browserPreferences';
import { liveTradingService } from '@/services/liveTradingService';
import { paperTradingService } from '@/services/paperTradingService';
import { tradeJournalService } from '@/services/tradeJournalService';

export function Settings() {
  const preferences = useBrowserPreferences();
  const [message, setMessage] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [sessions, setSessions] = useState({ live: 'Checking…', paper: 'Checking…' });
  const [exporting, setExporting] = useState(false);
  useEffect(() => {
    let active = true;
    setSessions({ live: 'Checking…', paper: 'Checking…' });
    void Promise.allSettled([liveTradingService.getStatus(), paperTradingService.getStatus()]).then(([live, paper]) => {
      if (!active) return;
      setSessions({ live: live.status === 'fulfilled' ? `${live.value.trading_mode ?? 'Live service'} · ${live.value.status}` : 'Unavailable',
        paper: paper.status === 'fulfilled' ? `${paper.value.status}${paper.value.recovery_required ? ' · recovery required' : ''}` : 'Unavailable' });
    });
    return () => { active = false; };
  }, [revision]);
  const save = (field: keyof typeof preferences, value: boolean) => {
    try { saveBrowserPreferences({ ...preferences, [field]: value }); setMessage('Saved for this browser.'); }
    catch { setMessage('This browser could not save your preference.'); }
  };
  const exportJournal = async () => {
    setExporting(true); setMessage(null);
    try {
      const response = await fetch(tradeJournalService.getExportUrl());
      if (!response.ok) throw new Error('Journal export unavailable. Try again when the backend is reachable.');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = 'trade_journal.csv'; link.click(); URL.revokeObjectURL(url);
      setMessage('Journal downloaded.');
    } catch (error) { setMessage(String(error)); }
    finally { setExporting(false); }
  };
  return <div className="page">
    <PageHead title="Settings" subtitle="Browser preferences and application configuration" icon={<span>⚙</span>} />
    {message && <p role="status">{message}</p>}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', gap: 18 }}>
      <section className="panel"><SectionHead title="Appearance" /><div style={{ padding: 20, display: 'grid', gap: 18 }}>
        <label><input type="checkbox" checked={preferences.tacticalBackground} onChange={e => save('tacticalBackground', e.target.checked)} /> Tactical background</label>
        <label><input type="checkbox" checked={preferences.reticle} onChange={e => save('reticle', e.target.checked)} /> Reticle overlay</label>
        <p>Changes apply immediately on this browser.</p>
      </div></section>
      <section className="panel"><SectionHead title="Trading configuration" /><div style={{ padding: 20, display: 'grid', gap: 14 }}>
        <p>Choose strategy, risk limits and execution settings in the setup page for the session you want to run.</p>
        <Link className="btn btn-cyan" to="/scanner">Manual scanner</Link>
        <Link className="btn" to="/training/range#setup">Paper bot setup</Link>
        <Link className="btn" to="/bot/setup">Live bot setup and preflight</Link>
        <Link to="/bot/status">Session status and shutdown recovery</Link>
      </div></section>
      <section className="panel"><SectionHead title="Backend sessions" /><div style={{ padding: 20 }}>
        <p>Live service: <Chip>{sessions.live}</Chip></p><p>Paper service: <Chip>{sessions.paper}</Chip></p>
        <p>Session status does not verify exchange credentials or permission to trade. Live setup runs the account preflight.</p>
        <button className="btn" onClick={() => setRevision(v => v + 1)}>Refresh status</button>
      </div></section>
      <section className="panel"><SectionHead title="Records and integrations" /><div style={{ padding: 20, display: 'grid', gap: 14 }}>
        <Link to="/journal">Review the trade journal</Link>
        <button className="btn" disabled={exporting} onClick={() => void exportJournal()}>{exporting ? 'Exporting…' : 'Download full journal CSV'}</button>
        <p>Exchange credentials are configured on the backend. This page does not store keys.</p>
        <p>Telegram, Discord, email alerts, account management and subscription management are not configured in this app.</p>
      </div></section>
    </div>
  </div>;
}

import { FooterStatus,PageHead,SectionHead } from '@/components/hud';
import { saveBrowserPreferences,useBrowserPreferences } from '@/services/browserPreferences';
import { useState } from 'react';
import { Link } from 'react-router-dom';

export function Settings() {
  const preferences = useBrowserPreferences();
  const [message, setMessage] = useState<string | null>(null);
  const save = (field: keyof typeof preferences, value: boolean) => {
    try { saveBrowserPreferences({ ...preferences, [field]: value }); setMessage('Saved for this browser.'); }
    catch { setMessage('This browser could not save your preference.'); }
  };
  return <div className="page">
    <PageHead title="Settings" subtitle="Appearance preferences for this browser" />
    {message && <p role="status">{message}</p>}
    <section className="panel"><SectionHead title="Appearance" /><div className="preferences-fields">
      <label><input type="checkbox" checked={preferences.tacticalBackground} onChange={e => save('tacticalBackground', e.target.checked)} /> Tactical background</label>
      <label><input type="checkbox" checked={preferences.reticle} onChange={e => save('reticle', e.target.checked)} /> Reticle overlay</label>
      <p>Changes apply immediately. These overlays are decorative and do not indicate session activity.</p>
    </div></section>
    <nav className="preferences-links" aria-label="Configuration and records">
      <Link className="btn" to="/scanner">Scanner inputs</Link>
      <Link className="btn" to="/training/range#setup">Paper session setup</Link>
      <Link className="btn" to="/bot/setup">Live preflight</Link>
      <Link className="btn" to="/bot/status">Session status and recovery</Link>
      <Link className="btn" to="/journal">Journal and CSV export</Link>
    </nav>
    <FooterStatus />
  </div>;
}

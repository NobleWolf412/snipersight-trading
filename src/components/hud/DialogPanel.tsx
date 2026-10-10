import { useState, type ReactNode } from 'react';
import { Modal } from './Modal';

/** Optional detail has one explicit entry point; configuration stays with its caller. */
export function DialogPanel({ label, trigger, summary, children, maxWidth = 760, icon = false }: {
  label: string; trigger?: ReactNode; summary?: ReactNode; children: ReactNode;
  maxWidth?: number; icon?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return <div className={icon ? 'help-dialog-entry' : 'dialog-entry'}>
    {summary && <div className="dialog-entry__summary">{summary}</div>}
    <button type="button" className={`btn${icon ? ' btn-icon' : ''}`} aria-label={label}
      aria-haspopup="dialog" onClick={() => setOpen(true)}>
      {icon ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
        <path d="M12 11v6M12 7v1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg> : trigger ?? label}
    </button>
    {open && <Modal label={label} onClose={() => setOpen(false)} maxWidth={maxWidth}>
      <div className="dialog-panel-content"><h2>{label}</h2>{children}</div>
    </Modal>}
  </div>;
}

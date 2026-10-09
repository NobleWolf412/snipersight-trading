import { useLayoutEffect,useRef,type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { lockDialogScroll } from './dialogScrollLock';

interface ModalProps {
  label: string;
  onClose: () => void;
  children: ReactNode;
  maxWidth?: number;
}

export function Modal({ label, onClose, children, maxWidth = 620 }: ModalProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const release = lockDialogScroll();
    element.showModal();
    return () => {
      element.close();
      release();
      if (trigger?.isConnected && trigger.getClientRects().length) trigger.focus();
      else document.querySelector<HTMLElement>('.hamburger, .brand')?.focus();
    };
  }, []);
  // Lifecycle close events never invoke onClose: StrictMode replays this effect.
  return createPortal(
    <dialog ref={dialog} className="modal-bg" aria-label={label}
      style={{ maxWidth }} tabIndex={-1}
      onClose={event => event.stopPropagation()}
      onCancel={event => { event.preventDefault(); event.stopPropagation(); onClose(); }}
      onClick={event => { event.stopPropagation(); if (event.target === event.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-controls">
          <button type="button" className="btn btn-icon" aria-label={`Close ${label}`} onClick={onClose}>Close</button>
        </div>
        {children}
      </div>
    </dialog>, document.body,
  );
}

// HUD Modal — backdrop + centered card.
// Port of prototype/shared.jsx Modal.
import type { ReactNode } from 'react';

interface ModalProps {
  onClose: () => void;
  children: ReactNode;
  maxWidth?: number;
}

export function Modal({ onClose, children, maxWidth }: ModalProps) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div
        className="modal"
        style={{ maxWidth: maxWidth || 620 }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

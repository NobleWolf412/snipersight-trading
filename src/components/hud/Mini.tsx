// HUD Mini — compact label/value tile (used inside panels).
// Port of prototype/shared.jsx Mini.
import type { ReactNode } from 'react';

interface MiniProps {
  label: string;
  value: ReactNode;
  accent?: boolean;
  bold?: boolean;
  valueColor?: string;
}

export function Mini({ label, value, accent, bold, valueColor }: MiniProps) {
  return (
    <div>
      <div
        className="mono"
        style={{
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 13,
          fontWeight: bold ? 800 : 600,
          color: valueColor || (accent ? 'var(--accent)' : 'var(--fg)'),
        }}
      >
        {value}
      </div>
    </div>
  );
}

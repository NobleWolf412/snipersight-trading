// HUD Chip — small pill label.
// Port of prototype/shared.jsx Chip.
import type { CSSProperties, ReactNode } from 'react';

export type ChipKind = 'accent' | 'green' | 'red' | 'amber' | 'blue' | 'purple';

interface ChipProps {
  kind?: ChipKind;
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
}

export function Chip({ kind, children, style, className }: ChipProps) {
  const cls = ['chip', kind ? `chip-${kind}` : '', className || ''].filter(Boolean).join(' ');
  return (
    <span className={cls} style={style}>
      {children}
    </span>
  );
}

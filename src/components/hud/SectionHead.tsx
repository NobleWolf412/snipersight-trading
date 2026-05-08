// HUD SectionHead — panel header strip with pulsing dot.
// Port of prototype/shared.jsx SectionHead.
import type { ReactNode } from 'react';

interface SectionHeadProps {
  title: ReactNode;
  right?: ReactNode;
}

export function SectionHead({ title, right }: SectionHeadProps) {
  return (
    <div className="sec-head">
      <div className="sec-title">
        <span className="dot" /> {title}
      </div>
      {right}
    </div>
  );
}

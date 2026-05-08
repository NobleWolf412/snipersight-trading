// HUD PageHead — page title row with icon, subtitle, and badges.
// Port of prototype/shared.jsx PageHead.
import type { ReactNode } from 'react';

interface PageHeadProps {
  icon?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  /** When 'red', the title is rendered in red (for live / alert states). */
  accent?: 'amber' | 'red';
}

export function PageHead({ icon, title, subtitle, badges, accent }: PageHeadProps) {
  return (
    <div className="page-head">
      <div className="page-title">
        {icon && <div className="icon">{icon}</div>}
        <div>
          <h1 className={accent === 'red' ? 'live' : ''}>{title}</h1>
          {subtitle && <div className="sub">{subtitle}</div>}
        </div>
      </div>
      {badges && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {badges}
        </div>
      )}
    </div>
  );
}

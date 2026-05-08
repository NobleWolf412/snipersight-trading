// HUD RiskBar — small horizontal limit bar with label.
// Port of prototype/shared.jsx RiskBar.

interface RiskBarProps {
  label: string;
  value: number;
  max: number;
  unit?: string;
  color?: string;
}

export function RiskBar({ label, value, max, unit, color }: RiskBarProps) {
  const pct = Math.min(100, (value / max) * 100);
  const c = color || 'var(--green-soft)';
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.18em',
            textTransform: 'uppercase',
          }}
        >
          {label}
        </span>
        <span className="mono" style={{ fontSize: 11, color: c, fontWeight: 700 }}>
          {value}
          {unit || ''} <span style={{ color: 'var(--fg-4)' }}>/ {max}{unit || ''}</span>
        </span>
      </div>
      <div
        style={{
          position: 'relative',
          height: 6,
          borderRadius: 3,
          background: 'rgba(0,0,0,.5)',
          overflow: 'hidden',
          border: '1px solid var(--border-soft)',
        }}
      >
        <div
          style={{
            height: '100%',
            width: pct + '%',
            background: `linear-gradient(90deg, ${c}, color-mix(in oklch, ${c} 60%, transparent))`,
            boxShadow: `0 0 10px ${c}`,
            transition: 'width .6s ease',
          }}
        />
      </div>
    </div>
  );
}

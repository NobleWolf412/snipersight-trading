import type { SourceRef, SourceTier } from './types';

const TIER_STYLE: Record<SourceTier, { label: string; color: string; bg: string }> = {
  primary:       { label: 'PRIMARY',  color: '#22d3ee', bg: 'rgba(34,211,238,.10)' },
  vendor:        { label: 'VENDOR',   color: '#fbbf24', bg: 'rgba(251,191,36,.10)' },
  supplementary: { label: 'SUPP',     color: 'var(--fg-4)', bg: 'rgba(255,255,255,.05)' },
};

export interface SourceListProps {
  sources: SourceRef[];
  title?: string;
}

export function SourceList({ sources, title = '// SOURCES' }: SourceListProps) {
  if (sources.length === 0) return null;
  return (
    <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px dashed var(--border-soft)' }}>
      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-4)',
          letterSpacing: '.24em',
          textTransform: 'uppercase',
          marginBottom: 10,
        }}
      >
        {title}
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
        {sources.map((s) => {
          const tier = TIER_STYLE[s.tier];
          return (
            <li key={s.url} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span
                className="mono"
                style={{
                  display: 'inline-block',
                  minWidth: 70,
                  textAlign: 'center',
                  fontSize: 9,
                  letterSpacing: '.18em',
                  fontWeight: 700,
                  color: tier.color,
                  background: tier.bg,
                  border: `1px solid ${tier.color}`,
                  borderRadius: 3,
                  padding: '2px 6px',
                }}
              >
                {tier.label}
              </span>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mono"
                style={{
                  fontSize: 12,
                  color: 'var(--fg-2)',
                  textDecoration: 'none',
                  borderBottom: '1px dotted var(--border-soft)',
                }}
              >
                {s.title}
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

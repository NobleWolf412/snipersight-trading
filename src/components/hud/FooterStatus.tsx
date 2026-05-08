// HUD FooterStatus — bottom status strip.
// Port of prototype/shared.jsx FooterStatus.
// In the real app this binds to backend health / build hash from the env.
import { Chip } from './Chip';

interface FooterStatusProps {
  /** Latency to backend, ms. */
  latency?: number;
  /** Build identifier (e.g. "1.0.0+abc1234"). */
  build?: string;
}

export function FooterStatus({ latency, build }: FooterStatusProps) {
  const now = Date.now();
  const ts = new Date(now).toISOString().slice(0, 19).replace('T', ' ') + 'Z';
  return (
    <div
      style={{
        marginTop: 24,
        padding: '12px 18px',
        border: '1px solid var(--border-soft)',
        borderRadius: 10,
        background: 'rgba(0,0,0,.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 14,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Chip kind="green">● BINANCE WS</Chip>
        <Chip kind="green">● PHEMEX REST</Chip>
        <Chip kind="green">● TELEGRAM</Chip>
        <Chip>● BACKEND {latency ?? 41}ms</Chip>
      </div>
      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-4)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
        }}
      >
        build {build ?? '1.0.0'} · {ts}
      </div>
    </div>
  );
}

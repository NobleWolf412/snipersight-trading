/** Scanner mode selection and advisory from the shared backend routing policy. */
import { Chip, Reticle, SectionHead } from '@/components/hud';
import { useScanner } from '@/context/ScannerContext';
import { useScannerRecommendation, recommendationIsFresh } from '@/hooks/useScannerRecommendation';
import type { ScannerMode, ScannerRecommendation } from '@/utils/api';

type AccentKey = 'cyan' | 'amber' | 'red' | 'green';

interface ModeMeta {
  /** Short tagline shown under the mode name. */
  tagline: string;
  /** Display accent colour. Hex resolved through ACCENT_HEX. */
  accent: AccentKey;
  /** Short marketing description (1 sentence). */
  desc: string;
  /** Trade-type pills shown on each card. */
  types: ('SWING' | 'INTRADAY' | 'SCALP')[];
}

// Display metadata keyed by mode name. The backend supplies operational
// fields (min_confluence_score, min_rr_ratio, timeframes, critical_TFs);
// this map supplies the visual treatment. Adding a new mode means adding
// an entry here AND in backend/shared/config/scanner_modes.py.
const MODE_META: Record<string, ModeMeta> = {
  overwatch: {
    tagline: 'Macro Surveillance',
    accent: 'cyan',
    desc: 'Swing trades · days–weeks · A+ macro setups only',
    types: ['SWING'],
  },
  strike: {
    tagline: 'Intraday Aggressive',
    accent: 'amber',
    desc: 'Hours · momentum + trend continuation · highest signal volume',
    types: ['SWING', 'INTRADAY', 'SCALP'],
  },
  surgical: {
    tagline: 'Precision',
    accent: 'red',
    desc: 'Minutes–hours · scalp + intraday · controlled risk only',
    types: ['INTRADAY', 'SCALP'],
  },
  stealth: {
    tagline: 'Balanced · Default',
    accent: 'green',
    desc: 'Balanced context · 1h planning · confirmed entries',
    types: ['INTRADAY', 'SCALP'],
  },
};

const ACCENT_HEX: Record<AccentKey, string> = {
  green: '#4ade80',
  amber: '#fbbf24',
  cyan: '#22d3ee',
  red: '#f87171',
};

// ─── Recommendation rule (deterministic) ─────────────────────────────────

// ─── Mode icon (per-mode line-art) ───────────────────────────────────────

function ModeIcon({ id, color }: { id: string; color: string }) {
  const stroke = {
    stroke: color,
    strokeWidth: 1.5,
    fill: 'none' as const,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  if (id === 'overwatch')
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1.5" fill={color} />
        <path d="M12 1 V4 M12 20 V23 M1 12 H4 M20 12 H23" />
      </svg>
    );
  if (id === 'strike')
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}>
        <path d="M13 2 L4 14 L11 14 L9 22 L20 9 L13 9 Z" fill={color} fillOpacity=".15" />
      </svg>
    );
  if (id === 'surgical')
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}>
        <path d="M3 21 L13 11 L17 7 L21 3 L21 7 L17 7 M13 11 L17 15" />
        <circle cx="6" cy="18" r="2" />
      </svg>
    );
  if (id === 'stealth')
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}>
        <path d="M12 3 L12 9 M9 6 L15 6" />
        <path d="M3 14 Q12 8 21 14 Q12 20 3 14 Z" />
        <circle cx="12" cy="14" r="2.5" fill={color} fillOpacity=".4" />
      </svg>
    );
  return null;
}

// ─── Score gauge ─────────────────────────────────────────────────────────

function ScoreGauge({ value, color, size = 44 }: { value: number; color: string; size?: number }) {
  const r = size / 2 - 4;
  const C = 2 * Math.PI * r;
  const dash = (value / 100) * C;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke="rgba(255,255,255,.06)"
        strokeWidth="3"
        fill="none"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke={color}
        strokeWidth="3"
        fill="none"
        strokeDasharray={`${dash} ${C}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
      <text
        x="50%"
        y="54%"
        textAnchor="middle"
        fill={color}
        fontFamily="Share Tech Mono, monospace"
        fontSize={size <= 44 ? '11' : '14'}
        fontWeight="700"
      >
        {value}
      </text>
    </svg>
  );
}

// ─── AI advisory hero ────────────────────────────────────────────────────

function ScannerRecommendationHero({
  rec,
  recMode,
  currentMode,
  onActivate,
}: {
  rec: ScannerRecommendation;
  recMode: ScannerMode | undefined;
  currentMode: string;
  onActivate: (id: string) => void;
}) {
  const meta = recMode ? MODE_META[recMode.name] : undefined;
  const color = meta ? ACCENT_HEX[meta.accent] : ACCENT_HEX.green;
  const isActive = currentMode === rec.mode;
  if (rec.status !== 'available' || !recMode || !meta) return (
    <section className="panel" style={{ padding: 24, marginBottom: 18 }} aria-live="polite">
      <strong>{rec.status === 'stand_aside' ? 'Wait for clearer conditions' : 'Recommendation unavailable'}</strong>
      <p>{rec.reason}</p><p>You can choose a fixed scanner mode below.</p>
    </section>
  );
  return (
    <section
      className="panel panel-accent"
      style={{ marginBottom: 18, position: 'relative', overflow: 'hidden' }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(ellipse 60% 80% at 70% 50%, ${color}18, transparent 60%)`,
          pointerEvents: 'none',
        }}
      />
      <Reticle />
      <div className="corner-tag tl">// MARKET GUIDANCE · RULE-BASED</div>
      <div className="corner-tag tr" style={{ color }}>
        {rec.regime?.composite?.replace(/_/g, ' ').toUpperCase()}
      </div>
      <div style={{ padding: '24px 26px', position: 'relative' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto',
            gap: 24,
            alignItems: 'center',
          }}
        >
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 10,
                flexWrap: 'wrap',
              }}
            >
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 9.5,
                  letterSpacing: '.22em',
                  color,
                  textTransform: 'uppercase',
                  padding: '3px 10px',
                  border: `1px solid ${color}55`,
                  background: `${color}11`,
                  borderRadius: 99,
                }}
              >
                <span
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: '50%',
                    background: color,
                    boxShadow: `0 0 8px ${color}`,
                  }}
                />
                MARKET GUIDANCE
              </span>
              <Chip kind="amber">◌ rule-based</Chip>
              <span
                className="mono"
                style={{ fontSize: 10, color: 'var(--fg-4)', letterSpacing: '.18em' }}
              >
                RECOMMENDED MODE
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 14,
                marginBottom: 8,
                flexWrap: 'wrap',
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontFamily: 'Share Tech Mono,monospace',
                  fontSize: 54,
                  letterSpacing: '.04em',
                  color,
                  textShadow: `0 0 18px ${color}66, 0 0 36px ${color}33`,
                  lineHeight: 0.95,
                }}
              >
                {recMode.name.toUpperCase()}
              </h2>
              <span
                className="mono"
                style={{
                  fontSize: 13,
                  color: 'var(--fg-2)',
                  letterSpacing: '.12em',
                  textTransform: 'uppercase',
                }}
              >
                {meta.tagline}
              </span>
            </div>
            <p
              style={{
                margin: '6px 0 14px',
                maxWidth: 680,
                fontSize: 14,
                lineHeight: 1.55,
                color: 'var(--fg-2)',
                borderLeft: `2px solid ${color}66`,
                paddingLeft: 12,
                fontStyle: 'italic',
              }}
            >
              {rec.reason}
            </p>
            <p style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              Daily BTC context · updated {rec.timestamp ? new Date(rec.timestamp).toLocaleTimeString() : '—'}.
              {' '}This suggests where to look; every setup still needs its own confirmation.
            </p>
            {isActive ? (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 18px',
                  border: `1.5px solid ${color}`,
                  background: `${color}14`,
                  borderRadius: 8,
                  fontFamily: 'Share Tech Mono,monospace',
                  fontSize: 13,
                  letterSpacing: '.22em',
                  color,
                  textTransform: 'uppercase',
                }}
              >
                ✓ Selected scanner mode
              </div>
            ) : (
              <button
                onClick={() => { if (rec.mode && recommendationIsFresh(rec)) onActivate(rec.mode); }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '12px 22px',
                  border: 'none',
                  background: color,
                  color: '#0a0a0a',
                  borderRadius: 8,
                  cursor: 'pointer',
                  fontFamily: 'Share Tech Mono,monospace',
                  fontSize: 13,
                  letterSpacing: '.22em',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  boxShadow: `0 0 0 1px ${color}, 0 0 24px ${color}66`,
                }}
              >
                USE {recMode.name.toUpperCase()}
              </button>
            )}
          </div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <ScoreGauge value={recMode.min_confluence_score} color={color} size={86} />
            <div
              className="mono"
              style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.20em' }}
            >
              MIN SCORE
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Mode card ───────────────────────────────────────────────────────────

function ModeCard({
  mode,
  meta,
  selected,
  recommended,
  onSelect,
}: {
  mode: ScannerMode;
  meta: ModeMeta;
  selected: boolean;
  recommended: boolean;
  onSelect: (id: string) => void;
}) {
  const color = ACCENT_HEX[meta.accent];
  const critical = mode.critical_timeframes ?? [];
  const primary = mode.primary_planning_timeframe ?? '—';
  const minRR = mode.min_rr_ratio ?? 1.5;
  return (
    <button
      type="button"
      onClick={() => onSelect(mode.name)}
      style={{
        position: 'relative',
        textAlign: 'left',
        padding: '16px 16px 14px',
        background: selected ? `linear-gradient(180deg, ${color}18, ${color}06)` : 'rgba(0,0,0,.40)',
        border: `1.5px solid ${selected ? color : 'var(--border-soft)'}`,
        borderRadius: 10,
        cursor: 'pointer',
        color: 'var(--fg)',
        fontFamily: 'inherit',
        boxShadow: selected
          ? `0 0 0 1px ${color}, 0 0 22px ${color}33, inset 0 0 30px ${color}10`
          : 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        minHeight: 200,
      }}
    >
      {recommended && (
        <span
          style={{
            position: 'absolute',
            top: -9,
            right: 14,
            padding: '2px 8px',
            background: '#0a0a0a',
            border: `1px solid ${color}`,
            color,
            borderRadius: 4,
            fontFamily: 'JetBrains Mono,monospace',
            fontSize: 8.5,
            letterSpacing: '.22em',
            fontWeight: 700,
          }}
        >
          ★ RECOMMENDED
        </span>
      )}
      {selected && (
        <span
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            fontFamily: 'JetBrains Mono,monospace',
            fontSize: 8.5,
            letterSpacing: '.22em',
            fontWeight: 700,
            color,
            padding: '2px 6px',
            border: `1px solid ${color}`,
            borderRadius: 3,
          }}
        >
          ● ACTIVE
        </span>
      )}

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            width: 34,
            height: 34,
            display: 'grid',
            placeItems: 'center',
            border: `1px solid ${color}55`,
            background: `${color}10`,
            borderRadius: 8,
          }}
        >
          <ModeIcon id={mode.name} color={color} />
        </div>
        <div>
          <div
            style={{
              fontFamily: 'Share Tech Mono,monospace',
              fontSize: 18,
              letterSpacing: '.14em',
              color: selected ? color : 'var(--fg)',
              textShadow: selected ? `0 0 10px ${color}55` : 'none',
            }}
          >
            {mode.name.toUpperCase()}
          </div>
          <div
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--fg-4)',
              letterSpacing: '.16em',
              textTransform: 'uppercase',
              marginTop: 2,
            }}
          >
            {meta.tagline}
          </div>
        </div>
      </div>

      {/* desc */}
      <div style={{ fontSize: 11.5, color: 'var(--fg-3)', lineHeight: 1.45, minHeight: 32 }}>
        {meta.desc}
      </div>

      {/* metric strip */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr 1fr',
          gap: 10,
          alignItems: 'center',
          padding: '8px 0',
          borderTop: '1px dashed var(--border-soft)',
          borderBottom: '1px dashed var(--border-soft)',
        }}
      >
        <ScoreGauge value={mode.min_confluence_score} color={color} size={40} />
        <div>
          <div
            className="mono"
            style={{ fontSize: 8.5, color: 'var(--fg-4)', letterSpacing: '.18em' }}
          >
            MIN R:R
          </div>
          <div className="mono" style={{ fontSize: 14, color, fontWeight: 700 }}>
            {minRR.toFixed(1)}
          </div>
        </div>
        <div>
          <div
            className="mono"
            style={{ fontSize: 8.5, color: 'var(--fg-4)', letterSpacing: '.18em' }}
          >
            PRIMARY
          </div>
          <div className="mono" style={{ fontSize: 14, color: 'var(--fg)', fontWeight: 700 }}>
            {primary}
          </div>
        </div>
      </div>

      {/* trade types */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {meta.types.map((t) => (
          <span
            key={t}
            className="chip"
            style={{
              fontSize: 8.5,
              color,
              borderColor: `${color}55`,
              background: `${color}10`,
              padding: '2px 7px',
            }}
          >
            {t}
          </span>
        ))}
      </div>

      {/* critical TFs */}
      <div style={{ marginTop: 'auto' }}>
        <div
          className="mono"
          style={{
            fontSize: 8.5,
            color: 'var(--fg-4)',
            letterSpacing: '.18em',
            marginBottom: 4,
          }}
        >
          CRITICAL · REJECTS IF MISSING
        </div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {mode.timeframes.map((tf) => {
            const isCritical = critical.includes(tf);
            return (
              <span
                key={tf}
                className="mono"
                style={{
                  fontSize: 9.5,
                  padding: '2px 6px',
                  borderRadius: 3,
                  color: isCritical ? color : 'var(--fg-4)',
                  background: isCritical ? `${color}14` : 'transparent',
                  border: `1px solid ${isCritical ? color + '66' : 'var(--border-soft)'}`,
                  fontWeight: isCritical ? 700 : 500,
                  letterSpacing: '.06em',
                }}
              >
                {tf}
                {isCritical ? ' ●' : ''}
              </span>
            );
          })}
        </div>
      </div>
    </button>
  );
}

// ─── Picker wrapper ──────────────────────────────────────────────────────

export function ScannerModePicker() {
  const { scannerModes, selectedMode, setSelectedMode } = useScanner();
  const rec = useScannerRecommendation();

  const recMode = scannerModes.find((m) => m.name === rec.mode);
  const currentName = selectedMode?.name ?? '';

  const handleActivate = (name: string) => {
    const m = scannerModes.find((x) => x.name === name);
    if (m) setSelectedMode(m);
  };

  return (
    <div style={{ marginBottom: 18 }}>
      <ScannerRecommendationHero
        rec={rec}
        recMode={recMode}
        currentMode={currentName}
        onActivate={handleActivate}
      />
      <section className="panel" style={{ position: 'relative' }}>
        <SectionHead
          title="Detection Modes"
          right={
            <>
              {selectedMode && <Chip kind="accent">{selectedMode.name.toUpperCase()}</Chip>}
              <Chip>SIGNAL CONFIG</Chip>
            </>
          }
        />
        <div className="corner-tag tl">// MODE-SELECT</div>
        <div className="corner-tag tr">{scannerModes.length} PROFILES</div>
        <div style={{ padding: '18px 18px 14px' }}>
          <div
            className="mono"
            style={{
              fontSize: 10,
              color: 'var(--fg-4)',
              letterSpacing: '.20em',
              textTransform: 'uppercase',
              marginBottom: 14,
            }}
          >
            // SCANNER · SETUPS FOR YOUR MANUAL REVIEW
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
            }}
            className="mode-grid"
          >
            {scannerModes
              .filter((m) => MODE_META[m.name])
              .map((m) => (
                <ModeCard
                  key={m.name}
                  mode={m}
                  meta={MODE_META[m.name]}
                  selected={currentName === m.name}
                  recommended={rec.mode === m.name}
                  onSelect={handleActivate}
                />
              ))}
          </div>
        </div>
      </section>

      <style>{`
        @media (max-width:1100px){
          .mode-grid{grid-template-columns:repeat(2,1fr) !important}
        }
      `}</style>
    </div>
  );
}

export default ScannerModePicker;

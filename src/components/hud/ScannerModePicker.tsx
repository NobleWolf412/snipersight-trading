/**
 * ScannerModePicker — Phase 3f sub-step 2
 *
 * Port of `prototype/scanner-modes.jsx` adapted to TSX. Renders the AI
 * advisory hero + 4 mode cards (OVERWATCH / STRIKE / SURGICAL / STEALTH)
 * and writes the operator's choice into ScannerContext via setSelectedMode.
 *
 * Real-data wiring:
 *   - `useScanner()` provides `scannerModes` (display source of truth — name,
 *     description, min_confluence_score, min_rr_ratio, critical_timeframes,
 *     primary_planning_timeframe, timeframes) and `selectedMode` for the
 *     active highlight.
 *   - `setSelectedMode(mode)` is called on card click — drives the global
 *     scanner mode for the bot AND any other listener of ScannerContext.
 *   - `useMarketRegime('scanner')` powers the AI advisory rule:
 *       BTC_DRIVE / ALTSEASON       → OVERWATCH (macro loaded)
 *       PANIC / DEFENSIVE           → SURGICAL  (precision under stress)
 *       CHOPPY / NEUTRAL / fallback → STEALTH   (balanced default)
 *     Snapshot fixture returns `{}` for /api/market/regime → hook produces
 *     its CHOPPY/MEDIUM default → recommendation lands on STEALTH
 *     deterministically.
 *
 * Synthetic-but-disclosed (amber `◌` chip pattern):
 *   - Display metadata (tagline, accent colour, bullet copy, trade-type
 *     pills) comes from a static MODE_META map keyed by mode name. The
 *     backend exposes the operational fields (min score, R:R, TFs) but
 *     not the display copy — so the docblock + a `◌` chip on the card
 *     header reflect that the visual treatment is local.
 *   - "AI advisory · rule-based" disclosure: this is a deterministic
 *     mapping from regime label to mode. A real LLM-driven recommendation
 *     would consume `api.getScannerRecommendation()` (already exists on
 *     /api/scanner/recommend) — that integration lands when the LLM
 *     reasoner is wired. For now the rule is transparent in the docblock
 *     and the hero badge text reads "AI ADVISORY · RULE-BASED" so no
 *     operator can mistake it for live ML.
 *
 * Determinism for snapshots:
 *   - No `Math.random` — recommendation is a pure function of regimeLabel.
 *   - No `setInterval`, no animation. Hover tints use CSS pseudo-classes
 *     are hard-disabled in snapshot mode by tests/visual/setup.ts'
 *     animation freeze.
 *
 * Snapshot-ready handshake:
 *   This component does NOT set `data-snapshot-ready` — it's mounted INSIDE
 *   `Scanner.tsx` which owns the page-level handshake. As long as this
 *   component's `useScanner()` and `useMarketRegime()` calls return their
 *   defaults synchronously (or within Playwright's networkidle window),
 *   the page is ready when Scanner.tsx flips its bit.
 */
import { useMemo } from 'react';
import { Chip, Reticle, SectionHead } from '@/components/hud';
import { useScanner } from '@/context/ScannerContext';
import { useMarketRegime } from '@/hooks/useMarketRegime';
import type { ScannerMode } from '@/utils/api';

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
    desc: 'Hours–days · cascades swing → intraday → scalp · all-around',
    types: ['SWING', 'INTRADAY', 'SCALP'],
  },
};

const ACCENT_HEX: Record<AccentKey, string> = {
  green: '#4ade80',
  amber: '#fbbf24',
  cyan: '#22d3ee',
  red: '#f87171',
};

// ─── Recommendation rule (deterministic) ─────────────────────────────────

interface Recommendation {
  mode: string;
  reason: string;
  confidence: 'HIGH' | 'MED' | 'LOW';
  regime: string;
}

function deriveRecommendation(regimeLabel: string, visibility: 'HIGH' | 'MEDIUM' | 'LOW'): Recommendation {
  // Macro-loaded regimes → patient swing surveillance.
  if (regimeLabel === 'BTC_DRIVE' || regimeLabel === 'ALTSEASON') {
    return {
      mode: 'overwatch',
      reason: `Macro-loaded regime detected (${regimeLabel}). Weekly + Daily structure is the cleanest signal source.`,
      confidence: visibility === 'HIGH' ? 'HIGH' : 'MED',
      regime: `MACRO · ${regimeLabel}`,
    };
  }
  // Defensive / panic → tighten to precision.
  if (regimeLabel === 'PANIC' || regimeLabel === 'DEFENSIVE') {
    return {
      mode: 'surgical',
      reason: `${regimeLabel} regime — controlled risk wins. Tighter stops, fewer cleaner setups.`,
      confidence: visibility === 'HIGH' ? 'HIGH' : 'MED',
      regime: `STRESS · ${regimeLabel}`,
    };
  }
  // Default: balanced.
  return {
    mode: 'stealth',
    reason: `Balanced regime (${regimeLabel || 'CHOPPY'}) — system default in effect; cascades swing → intraday → scalp.`,
    confidence: visibility === 'HIGH' ? 'MED' : 'LOW',
    regime: `BALANCED · ${regimeLabel || 'CHOPPY'}`,
  };
}

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
  rec: Recommendation;
  recMode: ScannerMode | undefined;
  currentMode: string;
  onActivate: (id: string) => void;
}) {
  const meta = recMode ? MODE_META[recMode.name] : undefined;
  const color = meta ? ACCENT_HEX[meta.accent] : ACCENT_HEX.green;
  const isActive = currentMode === rec.mode;
  if (!recMode || !meta) return null;
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
      <div className="corner-tag tl">// AI-ADVISORY · RULE-BASED</div>
      <div className="corner-tag tr" style={{ color }}>
        {rec.regime}
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
                AI ADVISORY · {rec.confidence} CONVICTION
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
              "{rec.reason}"
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
                ✓ Protocol Active
              </div>
            ) : (
              <button
                onClick={() => onActivate(rec.mode)}
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
                ⌬ ACTIVATE {recMode.name.toUpperCase()}
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
  const regime = useMarketRegime('scanner');

  // Visibility from useMarketRegime — narrow the type via runtime check so
  // deriveRecommendation receives only the three shape-allowed strings.
  const visibility: 'HIGH' | 'MEDIUM' | 'LOW' =
    regime.visibility === 'HIGH' || regime.visibility === 'LOW' ? regime.visibility : 'MEDIUM';

  const rec = useMemo(
    () => deriveRecommendation(regime.regimeLabel as string, visibility),
    [regime.regimeLabel, visibility],
  );

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
            // SCANNER · WHICH SIGNALS GET SURFACED TO THE BOT
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

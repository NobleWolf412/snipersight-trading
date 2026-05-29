import { useCallback, useEffect, useMemo, useState } from 'react';

export interface WeightFactor {
  name: string;
  subScore: number;
  baseWeight: number;
}

export interface WeightComparisonProfile {
  name: string;
  color?: string;
  weights: Record<string, number>;
}

export interface WeightSliderPanelProps {
  factors: WeightFactor[];
  threshold: number;
  comparisonProfiles?: WeightComparisonProfile[];
  onChange?: (weights: Record<string, number>, composite: number, passes: boolean) => void;
  compact?: boolean;
  thresholdLabel?: string;
  className?: string;
}

const PASS_COLOR = '#34d399';
const FAIL_COLOR = '#f87171';
const BASELINE_COLOR = 'var(--fg-4)';
const CURRENT_COLOR = '#fbbf24';

export function WeightSliderPanel({
  factors,
  threshold,
  comparisonProfiles = [],
  onChange,
  compact = false,
  thresholdLabel = 'PASS THRESHOLD',
  className,
}: WeightSliderPanelProps) {
  const baseWeights = useMemo(
    () => Object.fromEntries(factors.map((f) => [f.name, f.baseWeight])),
    [factors],
  );

  const [weights, setWeights] = useState<Record<string, number>>(baseWeights);

  // Reset to baseline whenever the factor set changes
  useEffect(() => {
    setWeights(baseWeights);
  }, [baseWeights]);

  // Duplicate factor.name in the input would silently collide (same record key
  // and React key). Warn so misuse is loud, not silent.
  useEffect(() => {
    const seen = new Set(factors.map((f) => f.name));
    if (seen.size !== factors.length) {
      console.warn(
        'WeightSliderPanel: duplicate factor names detected — sliders will collide',
      );
    }
  }, [factors]);

  const composite = useMemo(
    () =>
      factors.reduce(
        (sum, f) => sum + (weights[f.name] ?? 0) * f.subScore,
        0,
      ) * 100,
    [weights, factors],
  );

  const passes = composite >= threshold;

  useEffect(() => {
    onChange?.(weights, composite, passes);
  }, [weights, composite, passes, onChange]);

  const handleChange = useCallback(
    (factorName: string, raw: number) => {
      const newValue = Math.max(0, Math.min(1, raw));
      setWeights((prev) => {
        const oldValue = prev[factorName] ?? 0;
        const delta = newValue - oldValue;
        if (Math.abs(delta) < 1e-6) return prev;

        const otherTotal = Object.entries(prev)
          .filter(([k]) => k !== factorName)
          .reduce((sum, [, v]) => sum + v, 0);

        const next: Record<string, number> = { [factorName]: newValue };
        const newOtherTotal = Math.max(0, otherTotal - delta);
        for (const [name, w] of Object.entries(prev)) {
          if (name === factorName) continue;
          const scaled = otherTotal > 0 ? w * (newOtherTotal / otherTotal) : 0;
          next[name] = Math.max(0, scaled);
        }

        // Renormalize to 1.0 to compensate for FP drift. Degenerate all-zero
        // state (sum=0) is unreachable through normal slider drags but possible
        // via prop changes or rapid edge inputs; recover by restoring baseline
        // rather than returning a record that breaks the sum=1.0 invariant.
        const total = Object.values(next).reduce((s, v) => s + v, 0);
        if (total > 0 && Math.abs(total - 1.0) > 1e-4) {
          for (const k of Object.keys(next)) next[k] = next[k] / total;
        } else if (total <= 0) {
          for (const [name, baseW] of Object.entries(baseWeights)) {
            next[name] = baseW;
          }
        }
        return next;
      });
    },
    [baseWeights],
  );

  const reset = useCallback(() => setWeights(baseWeights), [baseWeights]);

  return (
    <div className={className} style={{ width: '100%' }}>
      {/* Composite + threshold + pass/fail */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr) auto',
          gap: 10,
          alignItems: 'center',
          padding: '10px 14px',
          border: '1px solid var(--border-soft)',
          borderRadius: 6,
          background: 'rgba(0,0,0,.4)',
          marginBottom: 12,
        }}
      >
        <Stat label="Composite" value={composite.toFixed(1)} color={passes ? PASS_COLOR : FAIL_COLOR} />
        <Stat label={thresholdLabel} value={threshold.toFixed(1)} color="var(--fg-2)" />
        <Stat
          label="Margin"
          value={`${composite >= threshold ? '+' : ''}${(composite - threshold).toFixed(1)}`}
          color={passes ? PASS_COLOR : FAIL_COLOR}
        />
        <span
          className="mono"
          style={{
            padding: '6px 14px',
            border: `1px solid ${passes ? PASS_COLOR : FAIL_COLOR}`,
            borderRadius: 4,
            color: passes ? PASS_COLOR : FAIL_COLOR,
            fontWeight: 800,
            fontSize: 11,
            letterSpacing: '.2em',
            background: `${passes ? PASS_COLOR : FAIL_COLOR}14`,
          }}
        >
          {passes ? '● PASS' : '○ FAIL'}
        </span>
      </div>

      {/* Per-factor rows */}
      <div style={{ display: 'grid', gap: compact ? 6 : 8 }}>
        {factors.map((f) => (
          <FactorRow
            key={f.name}
            factor={f}
            currentWeight={weights[f.name] ?? 0}
            baseWeight={f.baseWeight}
            comparisons={comparisonProfiles}
            onChange={(v) => handleChange(f.name, v)}
            compact={compact}
          />
        ))}
      </div>

      {/* Reset + comparison-profile legend */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 12,
          paddingTop: 10,
          borderTop: '1px dashed var(--border-soft)',
        }}
      >
        <div className="mono" style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em' }}>
          <span style={{ color: CURRENT_COLOR }}>▼ current</span>
          {'  '}
          <span style={{ color: BASELINE_COLOR }}>▽ baseline</span>
          {comparisonProfiles.map((p) => (
            <span key={p.name} style={{ color: p.color ?? '#60a5fa', marginLeft: 10 }}>
              ▽ {p.name}
            </span>
          ))}
        </div>
        <button
          type="button"
          onClick={reset}
          className="btn"
          style={{ fontSize: 10, padding: '6px 12px', letterSpacing: '.18em' }}
        >
          ↺ RESET
        </button>
      </div>
    </div>
  );
}

interface FactorRowProps {
  factor: WeightFactor;
  currentWeight: number;
  baseWeight: number;
  comparisons: WeightComparisonProfile[];
  onChange: (value: number) => void;
  compact: boolean;
}

function FactorRow({
  factor,
  currentWeight,
  baseWeight,
  comparisons,
  onChange,
  compact,
}: FactorRowProps) {
  const contribution = currentWeight * factor.subScore;
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '160px 1fr 70px' : '180px 1fr 80px',
        gap: 10,
        alignItems: 'center',
        padding: '6px 10px',
        background: 'rgba(0,0,0,.25)',
        border: '1px solid var(--border-soft)',
        borderRadius: 4,
      }}
    >
      <div>
        <div
          className="mono"
          style={{ fontSize: 11, color: 'var(--fg)', letterSpacing: '.04em' }}
        >
          {factor.name}
        </div>
        <div
          className="mono"
          style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em', marginTop: 1 }}
        >
          SCORE {(factor.subScore * 100).toFixed(0)}
        </div>
      </div>

      <div style={{ position: 'relative' }}>
        <input
          type="range"
          min={0}
          max={1}
          step={0.005}
          value={currentWeight}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label={`${factor.name} weight`}
          style={{
            width: '100%',
            accentColor: CURRENT_COLOR,
          }}
        />
        {/* Baseline tick */}
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: `${baseWeight * 100}%`,
            top: -2,
            transform: 'translateX(-50%)',
            color: BASELINE_COLOR,
            fontSize: 10,
            lineHeight: 1,
            pointerEvents: 'none',
          }}
        >
          ▽
        </span>
        {/* Comparison ticks */}
        {comparisons.map((p) => {
          const w = p.weights[factor.name];
          if (w == null) return null;
          return (
            <span
              key={p.name}
              aria-hidden
              title={`${p.name} = ${(w * 100).toFixed(1)}%`}
              style={{
                position: 'absolute',
                left: `${w * 100}%`,
                bottom: -2,
                transform: 'translateX(-50%)',
                color: p.color ?? '#60a5fa',
                fontSize: 9,
                lineHeight: 1,
                pointerEvents: 'none',
              }}
            >
              ▽
            </span>
          );
        })}
      </div>

      <div style={{ textAlign: 'right' }}>
        <div
          className="mono"
          style={{ fontSize: 13, color: CURRENT_COLOR, fontWeight: 800 }}
        >
          {(currentWeight * 100).toFixed(1)}%
        </div>
        <div
          className="mono"
          style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.14em' }}
        >
          +{(contribution * 100).toFixed(1)}
        </div>
      </div>
    </div>
  );
}

interface StatProps {
  label: string;
  value: string;
  color?: string;
}

function Stat({ label, value, color }: StatProps) {
  return (
    <div>
      <div
        className="mono"
        style={{ fontSize: 9, color: 'var(--fg-4)', letterSpacing: '.18em', textTransform: 'uppercase' }}
      >
        {label}
      </div>
      <div
        className="mono"
        style={{ fontSize: 20, color: color ?? 'var(--fg)', fontWeight: 800, lineHeight: 1.1 }}
      >
        {value}
      </div>
    </div>
  );
}

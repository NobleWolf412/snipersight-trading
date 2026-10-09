/** View of the application-owned scan job. Navigation never abandons a run. */
import { useEffect, useSyncExternalStore } from 'react';
import { scanRunService, scanIsBusy, summarizeRejections } from '@/services/scanRunService';
import { useScanner } from '@/context/ScannerContext';
import { Chip } from './Chip';
export { summarizeRejections } from '@/services/scanRunService';
type RejectionSnapshot = NonNullable<ReturnType<typeof summarizeRejections>>;
const REASON_LABELS: Record<string, string> = {
  low_confluence: 'LOW CONFLUENCE',
  no_data: 'NO DATA',
  risk_validation: 'RISK VALIDATION',
  no_trade_plan: 'NO TRADE PLAN',
  errors: 'PIPELINE ERROR',
  missing_critical_tf: 'MISSING CRITICAL TF',
  cooldown: 'COOLDOWN',
  regime_block: 'REGIME BLOCKED',
};

export function ScanController({ onComplete }: { onComplete?: () => void }) {
  const { selectedMode, scanConfig } = useScanner();
  const state = useSyncExternalStore(scanRunService.subscribe, scanRunService.getSnapshot);
  const autoScan = state.autoScan;
  const busy = scanIsBusy(state.status);
  useEffect(() => { onComplete?.(); }, [state.historyVersion, onComplete]);
  const progressPct = state.total > 0 ? Math.min(100, (state.progress / state.total) * 100) : 0;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '10px 14px',
        border: '1px solid var(--border-soft)',
        borderRadius: 6,
        background: 'rgba(0,0,0,.35)',
      }}
    >
      {/* Button row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {!busy && (
          <button
            className="btn btn-cyan"
            onClick={() => selectedMode && void scanRunService.start(selectedMode, { exchange: scanConfig.exchange, limit: scanConfig.topPairs, majors: scanConfig.categories.majors, altcoins: scanConfig.categories.altcoins, meme_mode: scanConfig.categories.memeMode, leverage: scanConfig.leverage, market_type: scanConfig.marketType, macro_overlay: scanConfig.macroOverlay, target_symbol: scanConfig.targetSymbol })}
            disabled={!selectedMode}
            style={{
              padding: '10px 20px',
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '.18em',
              opacity: selectedMode ? 1 : 0.45,
              cursor: selectedMode ? 'pointer' : 'not-allowed',
            }}
          >
            ▶ RUN SCAN
          </button>
        )}
        {busy && (
          <button
            className="btn btn-red"
            onClick={() => void scanRunService.cancel()}
            style={{
              padding: '10px 20px',
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '.18em',
            }}
          >
            ■ STOP
          </button>
        )}

        {/* Auto-scan toggle */}
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onClick={() => scanRunService.setAutoScan(!autoScan)}
        >
          <div
            style={{
              width: 32,
              height: 16,
              borderRadius: 8,
              background: autoScan ? 'var(--accent)' : 'rgba(0,0,0,.6)',
              border: '1px solid var(--border-soft)',
              position: 'relative',
              transition: 'background .15s',
              boxShadow: autoScan ? '0 0 6px var(--accent)' : 'none',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: 1,
                left: autoScan ? 17 : 1,
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: autoScan ? '#0a0c0e' : 'var(--fg-3)',
                transition: 'left .15s',
              }}
            />
          </div>
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: autoScan ? 'var(--accent)' : 'var(--fg-3)',
              letterSpacing: '.18em',
              textTransform: 'uppercase',
            }}
          >
            auto-scan {autoScan ? 'on' : 'off'}
          </span>
        </label>

        {/* Status chip — always one visible so the operator can always
            tell what the controller is doing at a glance. */}
        {state.status === 'idle' && <Chip>◌ IDLE</Chip>}
        {state.status === 'starting' && <Chip kind="amber">◌ STARTING…</Chip>}
        {state.status === 'queued' && <Chip kind="amber">QUEUED</Chip>}
        {state.status === 'cancelling' && <Chip kind="amber">STOP REQUESTED</Chip>}
        {state.status === 'disconnected' && <button className="btn btn-amber" onClick={scanRunService.reconnect}>RECONNECT</button>}
        {state.status === 'running' && <Chip kind="cyan">● SCANNING</Chip>}
        {state.status === 'completed' && (
          <Chip kind={state.signalsFound > 0 ? 'green' : 'amber'}>
            {state.signalsFound > 0 ? '✓' : '◌'} {state.signalsFound} SIGNALS
          </Chip>
        )}
        {state.status === 'cancelled' && <Chip kind="amber">◌ CANCELLED</Chip>}
        {state.status === 'failed' && <Chip kind="red">✕ FAILED</Chip>}
      </div>

      {/* Progress row — only visible while busy or for the last result */}
      {(busy || state.total > 0) && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div
            className="mono"
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              letterSpacing: '.16em',
              textTransform: 'uppercase',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>
              progress · {state.progress} / {state.total || '—'}
            </span>
            <span style={{ color: 'var(--fg-4)' }}>
              {state.currentSymbol ? `// ${state.currentSymbol}` : ''}
            </span>
          </div>
          <div
            style={{
              width: '100%',
              height: 4,
              background: 'rgba(0,0,0,.6)',
              border: '1px solid var(--border-soft)',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: '100%',
                height: '100%',
                transform: `scaleX(${progressPct / 100})`,
                transformOrigin: 'left center',
                background: 'var(--accent)',
                boxShadow: busy ? '0 0 6px var(--accent)' : 'none',
                transition: 'transform .35s ease-out',
              }}
            />
          </div>
        </div>
      )}

      {/* Error row */}
      {state.error && (
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--red-2)',
            letterSpacing: '.14em',
            textTransform: 'uppercase',
          }}
        >
          ✕ {state.error}
        </div>
      )}

      {/* Rejection breakdown — visible after any completed scan that
          recorded rejections. Bars are proportional within the strip
          (max-reason normalized to full width) so the operator sees
          relative dominance at a glance regardless of absolute scale. */}
      {state.rejections && state.rejections.byReason.length > 0 && (
        <RejectionBreakdownStrip
          rejections={state.rejections}
          signalsFound={state.signalsFound}
        />
      )}
    </div>
  );
}

// ─── RejectionBreakdownStrip ─────────────────────────────────────────────
// Stand-alone sub-component so the main controller render block stays
// scannable. Renders a stacked-by-count bar list with reason label,
// percentage of total, and up to three example symbols. The widest bar
// drives the visual scale — every other bar is relative width to it.

interface RejectionBreakdownStripProps {
  rejections: RejectionSnapshot;
  signalsFound: number;
}

function RejectionBreakdownStrip({ rejections, signalsFound }: RejectionBreakdownStripProps) {
  const maxCount = rejections.byReason[0]?.count ?? 1;
  return (
    <div
      style={{
        marginTop: 4,
        paddingTop: 8,
        borderTop: '1px dashed var(--border-soft)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>// rejection breakdown</span>
        <span style={{ color: 'var(--fg-4)' }}>
          {rejections.total} rejected · {signalsFound} kept
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {rejections.byReason.map(({ reason, count, examples }) => {
          const label = REASON_LABELS[reason] ?? reason.replace(/_/g, ' ').toUpperCase();
          const pct = rejections.total > 0
            ? Math.round((count / rejections.total) * 100)
            : 0;
          const widthPct = (count / maxCount) * 100;
          return (
            <div key={reason} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div
                className="mono"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 10,
                  color: 'var(--fg-2, var(--fg))',
                  letterSpacing: '.1em',
                }}
              >
                <span>
                  {label}
                  {examples.length > 0 && (
                    <span style={{ color: 'var(--fg-4)', marginLeft: 8, fontSize: 9 }}>
                      ({examples.join(', ')}
                      {count > examples.length ? '…' : ''})
                    </span>
                  )}
                </span>
                <span style={{ color: 'var(--fg-3)' }}>
                  {count} · {pct}%
                </span>
              </div>
              <div
                style={{
                  width: '100%',
                  height: 3,
                  background: 'rgba(0,0,0,.5)',
                  border: '1px solid var(--border-soft)',
                  borderRadius: 1,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: '100%',
                    height: '100%',
                    transform: `scaleX(${widthPct / 100})`,
                    transformOrigin: 'left center',
                    background: 'var(--amber, #fbbf24)',
                    opacity: 0.75,
                    transition: 'transform .35s ease-out',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

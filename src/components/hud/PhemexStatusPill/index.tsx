// PhemexStatusPill — always-visible Phemex integration health indicator.
// Lives in the Topbar (every page) so the operator sees data-pipe health
// at a glance without remembering to curl /healthz.
//
// Click expands a Modal with the full counter snapshot. Severity bumps:
//   - GREEN: all systems nominal (default)
//   - AMBER: stale frames, parse errors, REST 429s/5xx, backfill stale
//   - RED:   WS disconnected, REST/WS auth errors, balance fetch failing
//   - IDLE:  bot not running (everything quiet on purpose)
//
// Source contract: GET /api/integrations/phemex/healthz (already exists).

import { useCallback, useEffect, useRef, useState } from 'react';
import { liveTradingService } from '@/services/liveTradingService';
import { Chip, type ChipKind } from '../Chip';
import { Modal } from '../Modal';

interface PhemexHealth {
  status?: string;
  ws?: {
    enabled?: boolean;
    connected?: boolean;
    seconds_since_last_frame?: number | null;
    frames_in_total?: number;
    frames_aop_total?: number;
    parse_errors_total?: number;
    disconnects_total?: number;
    heartbeat_failures_total?: number;
    auth_errors_total?: number;
  };
  rest?: {
    rest_calls_total?: number;
    rest_5xx_total?: number;
    rest_429_total?: number;
    rest_auth_errors_total?: number;
    last_rest_error_msg?: string | null;
  };
  executor?: {
    fills_recorded_via_ws?: number;
    fills_recorded_via_rest?: number;
    fills_recovered_via_position_check?: number;
    balance_fetch_failures?: number;
  };
  backfill?: {
    runs_total?: number;
    errors_total?: number;
    rows_seen_total?: number;
    rows_new_total?: number;
    last_run_ts?: number | null;
    last_synced_ts?: number | null;
  };
  journal?: { session_rows?: number; total_rows?: number };
  in_memory?: { completed_trades?: number; pending_orders?: number };
}

type Severity = 'green' | 'amber' | 'red' | 'idle';

interface ClassifyResult {
  severity: Severity;
  reasons: string[];
}

function classify(health: PhemexHealth | null, isRunning: boolean): ClassifyResult {
  if (!isRunning) return { severity: 'idle', reasons: ['session not running'] };
  if (!health) return { severity: 'idle', reasons: ['no data yet'] };

  const reasons: string[] = [];
  let severity: Severity = 'green';
  const bump = (s: Severity) => {
    if (s === 'red') severity = 'red';
    else if (s === 'amber' && severity !== 'red') severity = 'amber';
  };

  if (health.ws?.enabled && health.ws?.connected === false) {
    bump('red');
    reasons.push('WS disconnected');
  }
  if ((health.rest?.rest_auth_errors_total ?? 0) > 0) {
    bump('red');
    reasons.push('REST auth errors');
  }
  if ((health.ws?.auth_errors_total ?? 0) > 0) {
    bump('red');
    reasons.push('WS auth errors');
  }
  if ((health.executor?.balance_fetch_failures ?? 0) > 0) {
    bump('red');
    reasons.push('balance fetch failing');
  }

  const sslf = health.ws?.seconds_since_last_frame;
  if (health.ws?.enabled && typeof sslf === 'number' && sslf > 60) {
    bump('amber');
    reasons.push(`no WS frame ${Math.round(sslf)}s`);
  }
  if ((health.ws?.parse_errors_total ?? 0) > 0) {
    bump('amber');
    reasons.push('WS parse errors');
  }
  if ((health.rest?.rest_429_total ?? 0) > 0) {
    bump('amber');
    reasons.push('REST 429s');
  }
  if ((health.rest?.rest_5xx_total ?? 0) > 0) {
    bump('amber');
    reasons.push('REST 5xx');
  }
  if ((health.backfill?.errors_total ?? 0) > 0) {
    bump('amber');
    reasons.push('backfill errors');
  }
  const lastRun = health.backfill?.last_run_ts;
  if (lastRun != null) {
    const ageMin = (Date.now() - lastRun) / 60_000;
    if (ageMin > 15) {
      bump('amber');
      reasons.push(`backfill stale ${Math.round(ageMin)}m`);
    }
  }

  if (severity === 'green') reasons.push('all systems nominal');
  return { severity, reasons };
}

const SEVERITY_LABEL: Record<Severity, string> = {
  green: 'PHEMEX OK',
  amber: 'PHEMEX WARN',
  red: 'PHEMEX FAIL',
  idle: 'PHEMEX IDLE',
};

const SEVERITY_TO_CHIP_KIND: Record<Severity, ChipKind | undefined> = {
  green: 'green',
  amber: 'amber',
  red: 'red',
  idle: undefined,
};

function formatTs(ts: number | null | undefined): string {
  if (!ts) return '—';
  return new Date(ts).toLocaleTimeString();
}

interface StatRowProps {
  label: string;
  value: React.ReactNode;
}

function StatRow({ label, value }: StatRowProps) {
  return (
    <div
      className="mono"
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        gap: 16,
        padding: '4px 0',
        borderBottom: '1px solid var(--border-soft)',
        fontSize: 11,
      }}
    >
      <span style={{ color: 'var(--fg-4)', letterSpacing: '.18em', textTransform: 'uppercase', fontSize: 10 }}>
        {label}
      </span>
      <span style={{ color: 'var(--fg)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

interface PhemexStatusPillProps {
  /** Poll interval in ms (default 10s — matches BotStatus idle cadence). */
  pollIntervalMs?: number;
}

export function PhemexStatusPill({ pollIntervalMs = 10_000 }: PhemexStatusPillProps) {
  const [health, setHealth] = useState<PhemexHealth | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const [healthData, statusData] = await Promise.all([
        liveTradingService.getPhemexHealth(),
        liveTradingService.getStatus().catch(() => null),
      ]);
      setHealth(healthData as PhemexHealth);
      setIsRunning(Boolean((statusData as { is_running?: boolean } | null)?.is_running));
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'healthz unreachable';
      setError(msg);
    }
  }, []);

  useEffect(() => {
    load();
    const tick = () => {
      timerRef.current = setTimeout(async () => {
        await load();
        tick();
      }, pollIntervalMs);
    };
    tick();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [load, pollIntervalMs]);

  const { severity, reasons } = classify(health, isRunning);
  const tooltip = error ? `Healthz error: ${error}` : reasons.join(' · ');
  const dot = severity === 'idle' ? '○' : '●';

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={tooltip}
        className={`chip ${SEVERITY_TO_CHIP_KIND[severity] ? `chip-${SEVERITY_TO_CHIP_KIND[severity]}` : ''}`}
        style={{
          cursor: 'pointer',
          background: 'inherit',
          font: 'inherit',
          letterSpacing: 'inherit',
        }}
      >
        {dot} {SEVERITY_LABEL[severity]}
      </button>

      {open && (
        <Modal onClose={() => setOpen(false)} maxWidth={680}>
          <div style={{ padding: 18 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 14,
                borderBottom: '1px solid var(--border-soft)',
                paddingBottom: 12,
              }}
            >
              <div className="hud" style={{ fontSize: 14, color: 'var(--fg)' }}>
                Phemex Integration · {SEVERITY_LABEL[severity]}
              </div>
              <Chip kind={SEVERITY_TO_CHIP_KIND[severity]}>{severity.toUpperCase()}</Chip>
            </div>

            {error && (
              <div
                className="mono"
                style={{
                  padding: '8px 12px',
                  marginBottom: 12,
                  border: '1px solid var(--red-border)',
                  background: 'var(--red-bg)',
                  borderRadius: 8,
                  color: 'var(--red-2)',
                  fontSize: 11,
                }}
              >
                Healthz fetch failed — {error}
              </div>
            )}

            {reasons.length > 0 && (
              <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 14 }}>
                {reasons.map((r, i) => (
                  <div key={i}>· {r}</div>
                ))}
              </div>
            )}

            {health && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                <div>
                  <div
                    className="hud"
                    style={{ fontSize: 11, color: 'var(--amber-2)', marginBottom: 8 }}
                  >
                    WebSocket
                  </div>
                  <StatRow
                    label="Connected"
                    value={
                      health.ws?.enabled
                        ? health.ws?.connected
                          ? 'yes'
                          : 'no'
                        : 'disabled'
                    }
                  />
                  <StatRow
                    label="Last frame"
                    value={
                      health.ws?.seconds_since_last_frame == null
                        ? '—'
                        : `${Math.round(health.ws.seconds_since_last_frame)}s ago`
                    }
                  />
                  <StatRow label="Frames in" value={health.ws?.frames_in_total ?? 0} />
                  <StatRow label="AOP frames" value={health.ws?.frames_aop_total ?? 0} />
                  <StatRow label="Parse errors" value={health.ws?.parse_errors_total ?? 0} />
                  <StatRow label="Disconnects" value={health.ws?.disconnects_total ?? 0} />
                  <StatRow label="Heartbeat fails" value={health.ws?.heartbeat_failures_total ?? 0} />
                </div>

                <div>
                  <div
                    className="hud"
                    style={{ fontSize: 11, color: 'var(--amber-2)', marginBottom: 8 }}
                  >
                    REST
                  </div>
                  <StatRow label="Calls" value={health.rest?.rest_calls_total ?? 0} />
                  <StatRow label="429s" value={health.rest?.rest_429_total ?? 0} />
                  <StatRow label="5xx" value={health.rest?.rest_5xx_total ?? 0} />
                  <StatRow label="Auth errors" value={health.rest?.rest_auth_errors_total ?? 0} />
                </div>

                <div>
                  <div
                    className="hud"
                    style={{ fontSize: 11, color: 'var(--amber-2)', marginBottom: 8 }}
                  >
                    Fills
                  </div>
                  <StatRow label="Via WS" value={health.executor?.fills_recorded_via_ws ?? 0} />
                  <StatRow label="Via REST poll" value={health.executor?.fills_recorded_via_rest ?? 0} />
                  <StatRow
                    label="Via position check"
                    value={health.executor?.fills_recovered_via_position_check ?? 0}
                  />
                  <StatRow label="Balance fail" value={health.executor?.balance_fetch_failures ?? 0} />
                </div>

                <div>
                  <div
                    className="hud"
                    style={{ fontSize: 11, color: 'var(--amber-2)', marginBottom: 8 }}
                  >
                    Backfill
                  </div>
                  <StatRow label="Runs" value={health.backfill?.runs_total ?? 0} />
                  <StatRow label="Errors" value={health.backfill?.errors_total ?? 0} />
                  <StatRow label="Rows new" value={health.backfill?.rows_new_total ?? 0} />
                  <StatRow label="Last run" value={formatTs(health.backfill?.last_run_ts)} />
                  <StatRow label="Last synced" value={formatTs(health.backfill?.last_synced_ts)} />
                </div>

                <div style={{ gridColumn: '1 / -1' }}>
                  <div
                    className="hud"
                    style={{ fontSize: 11, color: 'var(--amber-2)', marginBottom: 8 }}
                  >
                    Trade rows
                  </div>
                  <StatRow label="Journal · session" value={health.journal?.session_rows ?? 0} />
                  <StatRow label="Journal · total" value={health.journal?.total_rows ?? 0} />
                  <StatRow label="In memory" value={health.in_memory?.completed_trades ?? 0} />
                  <StatRow label="Pending orders" value={health.in_memory?.pending_orders ?? 0} />
                </div>
              </div>
            )}

            <div
              className="mono"
              style={{
                marginTop: 16,
                fontSize: 10,
                color: 'var(--fg-4)',
                letterSpacing: '.18em',
              }}
            >
              GET /api/integrations/phemex/healthz · refreshed every {Math.round(pollIntervalMs / 1000)}s
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

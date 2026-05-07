import { useEffect, useRef, useState, useCallback } from 'react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { liveTradingService } from '@/services/liveTradingService';

/**
 * Always-visible Phemex integration status pill.
 *
 * Sits next to the ModeBadge in BotStatus and turns amber/red when the
 * /api/integrations/phemex/healthz counters indicate degradation. The
 * point is that the operator never has to remember to run a curl — if
 * Phemex is sick, the pill says so where they're already looking.
 *
 * Click to open a drawer with the full counter snapshot.
 */

type PhemexHealth = {
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
};

type Severity = 'green' | 'amber' | 'red' | 'idle';

interface Props {
  /** Whether the bot session is currently running. Pill stays neutral when idle. */
  isRunning: boolean;
  /** Refresh interval in ms — match BotStatus's adaptive cadence. */
  pollIntervalMs?: number;
}

function classify(health: PhemexHealth | null, isRunning: boolean): {
  severity: Severity;
  reasons: string[];
} {
  if (!isRunning) return { severity: 'idle', reasons: ['session not running'] };
  if (!health) return { severity: 'idle', reasons: ['no data yet'] };

  const reasons: string[] = [];
  let severity: Severity = 'green';
  const bump = (s: Severity) => {
    // red beats amber beats green
    if (s === 'red') severity = 'red';
    else if (s === 'amber' && severity !== 'red') severity = 'amber';
  };

  // ── RED conditions ────────────────────────────────────────────────────
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

  // ── AMBER conditions ──────────────────────────────────────────────────
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

const SEVERITY_STYLES: Record<Severity, string> = {
  green: 'text-green-400 border-green-500/40 bg-green-500/10',
  amber: 'text-amber-400 border-amber-500/40 bg-amber-500/10 animate-pulse',
  red: 'text-red-400 border-red-500/50 bg-red-500/15 animate-pulse',
  idle: 'text-zinc-400 border-zinc-500/30 bg-zinc-500/5',
};

const SEVERITY_LABEL: Record<Severity, string> = {
  green: 'PHEMEX OK',
  amber: 'PHEMEX WARN',
  red: 'PHEMEX FAIL',
  idle: 'PHEMEX IDLE',
};

function formatTs(ts: number | null | undefined): string {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleTimeString();
}

function StatRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1 border-b border-white/5 last:border-b-0">
      <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">{label}</span>
      <span className="font-mono text-xs text-white/90 tabular-nums">{value}</span>
    </div>
  );
}

export function PhemexStatusPill({ isRunning, pollIntervalMs = 10_000 }: Props) {
  const [health, setHealth] = useState<PhemexHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await liveTradingService.getPhemexHealth();
      setHealth(data as PhemexHealth);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'healthz unreachable');
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

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={tooltip}
        className={cn(
          'text-[10px] font-black font-mono tracking-[0.2em] px-2 py-0.5 rounded-full border',
          'transition-colors hover:brightness-125 cursor-pointer',
          SEVERITY_STYLES[severity],
        )}
      >
        {SEVERITY_LABEL[severity]}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl bg-black/95 border border-white/10">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-mono text-sm uppercase tracking-widest text-white/80">
                Phemex Integration · {SEVERITY_LABEL[severity]}
              </h3>
              <span
                className={cn(
                  'text-[10px] font-black font-mono tracking-[0.2em] px-2 py-0.5 rounded-full border',
                  SEVERITY_STYLES[severity],
                )}
              >
                {severity.toUpperCase()}
              </span>
            </div>

            {error && (
              <div className="px-3 py-2 border border-red-500/40 bg-red-500/10 rounded text-red-400 font-mono text-xs">
                Healthz fetch failed — {error}
              </div>
            )}

            {reasons.length > 0 && (
              <div className="font-mono text-[11px] text-white/60">
                {reasons.map((r, i) => (
                  <div key={i}>· {r}</div>
                ))}
              </div>
            )}

            {health && (
              <div className="grid grid-cols-2 gap-x-6">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-amber-400/80 mb-1">
                    WebSocket
                  </div>
                  <StatRow
                    label="Connected"
                    value={
                      health.ws?.enabled
                        ? health.ws?.connected ? 'yes' : 'no'
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
                  <div className="font-mono text-[10px] uppercase tracking-widest text-amber-400/80 mb-1">
                    REST
                  </div>
                  <StatRow label="Calls" value={health.rest?.rest_calls_total ?? 0} />
                  <StatRow label="429s" value={health.rest?.rest_429_total ?? 0} />
                  <StatRow label="5xx" value={health.rest?.rest_5xx_total ?? 0} />
                  <StatRow label="Auth errors" value={health.rest?.rest_auth_errors_total ?? 0} />
                  {health.rest?.last_rest_error_msg && (
                    <StatRow
                      label="Last error"
                      value={
                        <span className="text-red-400 truncate max-w-[160px]" title={health.rest.last_rest_error_msg}>
                          {health.rest.last_rest_error_msg}
                        </span>
                      }
                    />
                  )}
                </div>

                <div className="mt-3">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-amber-400/80 mb-1">
                    Fills
                  </div>
                  <StatRow label="Via WS" value={health.executor?.fills_recorded_via_ws ?? 0} />
                  <StatRow label="Via REST poll" value={health.executor?.fills_recorded_via_rest ?? 0} />
                  <StatRow
                    label="Via position check"
                    value={health.executor?.fills_recovered_via_position_check ?? 0}
                  />
                  <StatRow
                    label="Balance fail"
                    value={health.executor?.balance_fetch_failures ?? 0}
                  />
                </div>

                <div className="mt-3">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-amber-400/80 mb-1">
                    Backfill
                  </div>
                  <StatRow label="Runs" value={health.backfill?.runs_total ?? 0} />
                  <StatRow label="Errors" value={health.backfill?.errors_total ?? 0} />
                  <StatRow label="Rows new" value={health.backfill?.rows_new_total ?? 0} />
                  <StatRow label="Last run" value={formatTs(health.backfill?.last_run_ts)} />
                  <StatRow label="Last synced" value={formatTs(health.backfill?.last_synced_ts)} />
                </div>

                <div className="mt-3 col-span-2">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-amber-400/80 mb-1">
                    Trade rows
                  </div>
                  <StatRow label="Journal · session" value={health.journal?.session_rows ?? 0} />
                  <StatRow label="Journal · total" value={health.journal?.total_rows ?? 0} />
                  <StatRow label="In memory" value={health.in_memory?.completed_trades ?? 0} />
                  <StatRow label="Pending orders" value={health.in_memory?.pending_orders ?? 0} />
                </div>
              </div>
            )}

            <div className="text-[10px] font-mono text-white/30 pt-2">
              Endpoint: GET /api/integrations/phemex/healthz · refreshed every {Math.round(pollIntervalMs / 1000)}s
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/**
 * KillZoneStrip — 24h overlay showing the four SMC kill zones with the
 * currently-active zone glowing + a status caption (Phase 5 polish).
 *
 * Plan reference: peppy-sniffing-owl §3c / §5b — "Kill-zone overlay
 * rendered on Intel charts (current kill-zone shaded; aligned with
 * `backend/strategy/smc/sessions.py::get_current_kill_zone`)". Closes
 * the deferred entry in Intel.tsx (placeholder line under SessionStrip).
 *
 * Layout
 *   ┌── 24h UTC ────────────────────────────────────────────────────┐
 *   │ ████ LDN-OPEN    ███ LDN-CLOSE  ███████ NY-OPEN  ████ ASIA   │
 *   └────────────────────▲ now────────────────────────────────────┘
 *   active: NEW_YORK_OPEN · ends in 1h 12m
 *
 * Real-data wiring
 *   - Single fetch on mount (zones are time-of-day; we recompute on
 *     reload). 30s poll keeps the countdown caption fresh without
 *     hammering the endpoint.
 *   - `now_utc` is taken from the response so the strip's playhead
 *     stays consistent with the backend's clock (avoids client/server
 *     skew jitter on the visual marker).
 *   - On error → muted strip with amber `◌` chip; no fake bands. This
 *     mirrors the established CooldownsTile / MacroScoreTile pattern.
 *
 * Symmetry (CLAUDE.md §10 #3)
 *   - Direction-agnostic surface (kill zones aren't long/short).
 *
 * StrictMode safety
 *   - cancelled flag + setTimeout cleanup, mirrors UniversePanel /
 *     CycleHeartbeat / CooldownsTile pattern.
 */
import { useEffect, useMemo, useState } from 'react';
import { api, type KillZoneStatus, type KillZoneWindow } from '@/utils/api';

const POLL_MS = 30_000;

const ZONE_COLORS: Record<string, string> = {
  london_open: '#fbbf24',
  new_york_open: '#22c55e',
  london_close: '#a78bfa',
  asian_open: '#60a5fa',
};

const ZONE_LABELS: Record<string, string> = {
  london_open: 'LDN OPEN',
  new_york_open: 'NY OPEN',
  london_close: 'LDN CLOSE',
  asian_open: 'ASIA OPEN',
};

function fmtCountdown(s: number | null): string {
  if (s == null || s <= 0) return '0s';
  if (s < 60) return `${s}s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const ss = s % 60;
    return ss > 0 ? `${m}m ${ss}s` : `${m}m`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

/**
 * Convert a zone window to one or two render segments on the 24h scale.
 * Returns array of {leftPct, widthPct} — single entry for normal windows,
 * two entries when the zone wraps midnight UTC (e.g. Asian Open is
 * 19-22 EST = 00-03 UTC, doesn't wrap; but London Open is 02-05 EST =
 * 07-10 UTC, also doesn't. Wrap support kept for future zone tables).
 */
function zoneSegments(z: KillZoneWindow): Array<{ left: number; width: number }> {
  const startMin = z.start_utc_hour * 60 + z.start_utc_minute;
  const endMin = z.end_utc_hour * 60 + z.end_utc_minute;
  const totalMin = 24 * 60;
  if (endMin >= startMin) {
    return [{ left: (startMin / totalMin) * 100, width: ((endMin - startMin) / totalMin) * 100 }];
  }
  // Wraps midnight UTC: render two segments.
  return [
    { left: (startMin / totalMin) * 100, width: ((totalMin - startMin) / totalMin) * 100 },
    { left: 0, width: (endMin / totalMin) * 100 },
  ];
}

export function KillZoneStrip() {
  const [data, setData] = useState<KillZoneStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const res = await api.getKillZoneStatus();
        if (cancelled) return;
        if (res.error) {
          setError(res.error);
        } else if (res.data) {
          setData(res.data);
          setError(null);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'fetch failed');
      } finally {
        if (!cancelled) setLoaded(true);
        if (!cancelled) timer = setTimeout(tick, POLL_MS);
      }
    };

    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const nowPct = useMemo(() => {
    if (!data) return null;
    const d = new Date(data.now_utc);
    if (Number.isNaN(d.getTime())) return null;
    return ((d.getUTCHours() * 60 + d.getUTCMinutes()) / (24 * 60)) * 100;
  }, [data]);

  if (error || !loaded || !data) {
    const reason = error ? `awaiting · ${error.slice(0, 48)}` : 'loading';
    return (
      <div
        className="mono"
        style={{
          marginTop: 8,
          fontSize: 9,
          color: 'var(--amber)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
        }}
      >
        ◌ kill-zone overlay · {reason}
      </div>
    );
  }

  const currentName = data.current;

  return (
    <div style={{ marginTop: 12 }}>
      <div
        className="mono"
        style={{
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.20em',
          textTransform: 'uppercase',
          marginBottom: 6,
        }}
      >
        // KILL ZONES · UTC
      </div>
      <div
        style={{
          position: 'relative',
          height: 28,
          border: '1px solid var(--border-soft)',
          borderRadius: 4,
          background: 'rgba(0,0,0,.35)',
          overflow: 'hidden',
        }}
      >
        {data.zones.map((z) => {
          const active = z.name === currentName;
          const color = ZONE_COLORS[z.name] ?? 'var(--accent)';
          return zoneSegments(z).map((seg, i) => (
            <div
              key={`${z.name}-${i}`}
              title={ZONE_LABELS[z.name] ?? z.name}
              style={{
                position: 'absolute',
                top: 4,
                bottom: 4,
                left: `${seg.left}%`,
                width: `${seg.width}%`,
                background: active
                  ? `linear-gradient(90deg, ${color}55, ${color}aa)`
                  : `${color}1a`,
                border: `1px solid ${color}${active ? 'cc' : '44'}`,
                borderRadius: 2,
                boxShadow: active ? `0 0 6px ${color}88` : 'none',
                display: 'flex',
                alignItems: 'center',
                padding: '0 4px',
                overflow: 'hidden',
              }}
            >
              {seg.width > 4 && (
                <span
                  className="mono"
                  style={{
                    fontSize: 8,
                    letterSpacing: '.14em',
                    color: active ? color : 'var(--fg-4)',
                    fontWeight: active ? 700 : 400,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {ZONE_LABELS[z.name] ?? z.name}
                </span>
              )}
            </div>
          ));
        })}
        {nowPct != null && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${nowPct}%`,
              width: 2,
              background: 'var(--accent)',
              boxShadow: '0 0 6px var(--accent)',
              zIndex: 2,
            }}
          />
        )}
      </div>
      <div
        className="mono"
        style={{
          marginTop: 6,
          fontSize: 9,
          letterSpacing: '.18em',
          textTransform: 'uppercase',
          color: currentName ? 'var(--accent)' : 'var(--fg-3)',
        }}
      >
        {currentName ? (
          <>
            ● ACTIVE · {ZONE_LABELS[currentName] ?? currentName}
            {data.current_ends_seconds != null && (
              <span style={{ color: 'var(--fg-4)' }}>
                {' '}
                · ends in {fmtCountdown(data.current_ends_seconds)}
              </span>
            )}
          </>
        ) : (
          <>
            ○ NO ZONE ACTIVE
            {data.next && data.next_starts_seconds != null && (
              <span style={{ color: 'var(--fg-4)' }}>
                {' '}
                · next {ZONE_LABELS[data.next] ?? data.next} in{' '}
                {fmtCountdown(data.next_starts_seconds)}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}

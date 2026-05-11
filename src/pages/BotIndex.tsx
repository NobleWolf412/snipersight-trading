/**
 * BotIndex — /bot route entry point.
 *
 * Probes liveTradingService.getStatus() on mount and routes to either:
 *   - /bot/status   if a bot is currently running
 *   - /bot/setup    otherwise (including probe failure — safe default
 *                   since setup re-probes and self-redirects too)
 *
 * Uses `replace: true` so the back button skips over /bot rather than
 * trapping the user in a redirect oscillation.
 *
 * Why this exists:
 *   Topbar's "Bot" link targets `/bot` (matches both /bot/setup and
 *   /bot/status via matchPrefixes). Before this index existed, clicking
 *   the nav link landed on an unregistered route and rendered nothing —
 *   the user saw a blank page + "No routes matched location \"/bot\""
 *   console error.
 *
 * Source of truth:
 *   liveTradingService.getStatus() — same endpoint BotSetup uses for its
 *   already-running guard (line 411). Returns `{status: 'running' | ...}`.
 *   Single shared source keeps the two redirect decisions consistent.
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { liveTradingService } from '@/services/liveTradingService';

export function BotIndex() {
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    liveTradingService
      .getStatus()
      .then((s) => {
        if (cancelled) return;
        if (s.status === 'running') navigate('/bot/status', { replace: true });
        else navigate('/bot/setup', { replace: true });
      })
      .catch((e) => {
        if (cancelled) return;
        // Backend unreachable or transient error — default to setup.
        // Setup's own preflight will surface the connectivity problem
        // with proper UI; we don't try to render an error here.
        console.warn('[BotIndex] status probe failed, routing to /bot/setup:', e);
        navigate('/bot/setup', { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  // Brief flash while the probe resolves. Matches the LoadingFallback look.
  return (
    <div
      style={{
        minHeight: '60vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--accent)',
        fontSize: 13,
      }}
      className="hud"
    >
      Routing to bot…
    </div>
  );
}

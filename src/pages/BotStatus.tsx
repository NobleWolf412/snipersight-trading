import { accountingColor,accountingLabel,executionReportNotice } from '../services/accounting';
import { BotPositions } from './BotPositions';
import { buildBotStatusViewModel } from './botStatusViewModel';
import { useBotStatusController } from './useBotStatusController';
/** Monitor one selected session owner. Commands remain owner-specific. */
import {
Chip,
ConfluenceBreakdown,
CycleHeartbeat,
DiagnoseWizard,
FooterStatus,
GauntletBreakdown,
MacroBand,
PageHead,
PipelineTracer,
PositionDetailModal,
Reticle,
SectionHead,
UniversePanel
} from '@/components/hud';
import { liveShutdownMessage } from '@/services/liveTradingService';


import { EquitySparkline,fmtCurrency,fmtDuration,fmtPct,MetricTile,ModePill,StatusPill,type SessionStatusValue } from './BotStatusViews';

export function BotStatus() {
  const { navigate, scannerModes, selectedMode, session, status, trades, loading, stopping, resetting, killing, showKillConfirm, setShowKillConfirm, error, analyzing, analyzeOutput, analyzeError, connectionError, tradesError, lifetime, lifetimeError, tracerSignalId, setTracerSignalId, diagnoseOpen, setDiagnoseOpen, diagnoseOpenedAtMs, setDiagnoseOpenedAtMs, detailSelection, setDetailSelection, cancelKillRef, now, handleStop, handleKillSwitch, handleReset, handleAnalyze } = useBotStatusController();
  const { lifecycle, isStarting, isRunning, isKilled, liveServiceSelected, needsRecovery, tradingMode, isLive, isPaper, canKillSwitch, canAnalyzeSession, stats, balance, initialBalance, positions, pendingOrders, signalLog, regime, liveStatus, cfg, subtitleText, headAccent } = buildBotStatusViewModel(session);

  return (
    <div className="page-shell" id="main-content">
      <Reticle />

      <PageHead
        icon="●"
        title={isPaper ? 'Paper session' : isLive ? 'Live session' : tradingMode === 'testnet' ? 'Testnet session' : 'Session status'}
        subtitle={subtitleText}
        accent={headAccent}
        badges={
          <>
            <ModePill mode={tradingMode} />
            <StatusPill status={(lifecycle && ['starting', 'stopping', 'recovering'].includes(lifecycle.phase)
              ? lifecycle.phase : status?.status ?? 'idle') as SessionStatusValue} />
          </>
        }
      />

      {/* ── Error banners ─────────────────────────────────────────── */}
      {connectionError && (
        <div
          style={{
            margin: '14px 0',
            padding: '12px 14px',
            border: '1px solid var(--amber)',
            borderRadius: 10,
            background: 'rgba(234,179,8,.08)',
            color: 'var(--amber)',
            fontSize: 12,
          }}
        >
          ⚠ {connectionError}
        </div>
      )}
      {error && (
        <div
          style={{
            margin: '14px 0',
            padding: '12px 14px',
            border: '1px solid var(--red)',
            borderRadius: 10,
            background: 'rgba(239,68,68,.08)',
            color: 'var(--red)',
            fontSize: 12,
          }}
        >
          ⚠ {error}
        </div>
      )}

      {loading && !status && (
        <div
          className="panel"
          style={{
            margin: '14px 0',
            padding: 32,
            textAlign: 'center',
            color: 'var(--fg-3)',
          }}
        >
          <span className="mono" style={{ letterSpacing: '.2em' }}>
            READING TELEMETRY…
          </span>
        </div>
      )}

      {status && (
        <div style={{ display: 'grid', gap: 14, marginTop: 14 }}>
          {/* ── Command Center ─────────────────────────────────── */}
          <section
            className="panel panel-accent"
            style={{
              padding: 18,
              // Priority: live > paper > running > idle. Live mode (real
              // money) is the loudest state. Paper mode running stays amber
              // (sandbox demarcation per project memory); non-paper running
              // gets green to signal "active state OK"; idle is amber.
              borderColor: isLive
                ? 'var(--red-border)'
                : isPaper
                  ? 'var(--amber-border)'
                  : isRunning
                    ? 'var(--green-border)'
                    : 'var(--amber-border)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 14,
                flexWrap: 'wrap',
              }}
            >
              {/* Session PnL hero. Single most important number on the page
                  for a running bot. Color follows sign (green up / red down /
                  fg-2 neutral). Sub-line carries record + active counts. */}
              <div style={{ minWidth: 0 }}>
                <div
                  className="mono"
                  style={{
                    fontSize: 32,
                    fontWeight: 800,
                    lineHeight: 1,
                    letterSpacing: '-0.01em',
                    color:
                      (balance?.pnl ?? 0) > 0
                        ? 'var(--green)'
                        : (balance?.pnl ?? 0) < 0
                          ? 'var(--red)'
                          : 'var(--fg-2)',
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: 10,
                    flexWrap: 'wrap',
                  }}
                >
                  <span>{fmtCurrency(balance?.pnl)}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, opacity: 0.85 }}>
                    {fmtPct(balance?.pnl_pct)}
                  </span>
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.22em',
                    textTransform: 'uppercase',
                    marginTop: 8,
                  }}
                >
                  Session PnL · {stats?.winning_trades ?? 0}W/{stats?.losing_trades ?? 0}L
                  {' · '}{positions.length} open · {pendingOrders.length} pending
                </div>
                {/* Lifetime cumulative — cross-session, sourced from the
                    journal aggregate. Distinct from the hero number, which
                    is current-session equity − initial. Renders as a
                    secondary strip so the operator can compare at a glance
                    without giving up the session-level focus. */}
                <div
                  className="mono"
                  title="Realized cumulative profit/loss across every closed trade in the journal — survives bot restarts and pre-dates this session."
                  style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.22em',
                    textTransform: 'uppercase',
                    marginTop: 4,
                  }}
                >
                  Cumulative P/L (all sessions){' '}
                  <strong
                    style={{
                      color: lifetime
                        ? lifetime.total_pnl > 0
                          ? 'var(--green)'
                          : lifetime.total_pnl < 0
                            ? 'var(--red)'
                            : 'var(--fg-2)'
                        : 'var(--fg-3)',
                      fontWeight: 800,
                    }}
                  >
                    {lifetime
                      ? fmtCurrency(lifetime.total_pnl)
                      : lifetimeError
                        ? '—'
                        : '…'}
                  </strong>
                  {lifetime && (
                    <>
                      {' · '}
                      <span style={{ color: 'var(--fg-3)' }}>
                        {lifetime.total_trades} trades · WR{' '}
                        {lifetime.win_rate.toFixed(0)}%
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignSelf: 'flex-start' }}>
                {isRunning ? (
                  <>
                    <button
                      type="button"
                      className="btn btn-red"
                      onClick={handleStop}
                      disabled={stopping}
                      style={{ fontSize: 11 }}
                      aria-label={stopping ? 'Stopping bot' : 'Stop bot gracefully'}
                    >
                      {stopping ? '↻ STOPPING' : '■ STOP'}
                    </button>
                    {/* Kill switch is live-only (no real positions to close
                        at market in paper). Hidden when canKillSwitch=false. */}
                    {canKillSwitch && (
                      <button
                        type="button"
                        className="btn btn-red"
                        onClick={() => setShowKillConfirm(true)}
                        style={{ fontSize: 11 }}
                        aria-label="Kill switch — stop entries and request closure"
                      >
                        ☠ KILL
                      </button>
                    )}
                  </>
                ) : (
                  <>
                    {needsRecovery && (
                      <button type="button" className="btn btn-red" onClick={handleStop} disabled={stopping}>
                        {stopping ? 'CHECKING RECOVERY' : 'RETRY SHUTDOWN'}
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-green"
                      onClick={() => navigate(session?.isPaper ? '/training/range#setup' : '/bot/setup')}
                      style={{ fontSize: 11 }}
                      aria-label="Reconfigure bot — return to setup page"
                      disabled={!!needsRecovery || isStarting}
                    >
                      ▶ RECONFIGURE
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={handleReset}
                      style={{ fontSize: 11 }}
                      aria-label="Reset bot session"
                      disabled={resetting || !!needsRecovery || (liveServiceSelected ? !lifecycle?.reset_allowed : (status && 'reset_allowed' in status && status.reset_allowed === false))}
                    >
                      {resetting ? 'VERIFYING ACCOUNT' : '↺ RESET'}
                    </button>
                  </>
                )}
                {/* AnalyzeSession is live-only (paper service has no
                    equivalent backend pipeline). Hidden for paper sessions. */}
                {canAnalyzeSession && (
                  <button
                    type="button"
                    className="btn btn-blue"
                    onClick={handleAnalyze}
                    disabled={analyzing}
                    style={{ fontSize: 11 }}
                    aria-label={analyzing ? 'Analyzing session' : 'Analyze current session'}
                  >
                    {analyzing ? '↻ ANALYZING' : '⊞ ANALYZE'}
                  </button>
                )}
              </div>
            </div>

            {/* Kill confirm */}
            {showKillConfirm && (
              <div
                style={{
                  marginTop: 14,
                  padding: 14,
                  border: '1px solid var(--red)',
                  borderRadius: 10,
                  background: 'rgba(239,68,68,.08)',
                }}
              >
                <div
                  className="mono"
                  style={{
                    fontWeight: 700,
                    color: 'var(--red)',
                    fontSize: 12,
                    marginBottom: 6,
                  }}
                >
                  ☠ CONFIRM KILL SWITCH
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-2)', marginBottom: 10 }}>
                  Stop new entries, cancel pending entries, and request market exits. Unconfirmed orders and exits remain under recovery.
                  {isLive && ' This uses real money.'}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    ref={cancelKillRef}
                    type="button"
                    className="btn"
                    onClick={() => setShowKillConfirm(false)}
                    style={{ fontSize: 10 }}
                    aria-label="Cancel kill switch — keep bot running"
                  >
                    CANCEL
                  </button>
                  <button
                    type="button"
                    className="btn btn-red"
                    onClick={handleKillSwitch}
                    disabled={killing}
                    style={{ fontSize: 10 }}
                    aria-label={killing ? 'Executing kill switch' : 'Confirm kill switch — request shutdown'}
                  >
                    {killing ? '↻ EXECUTING' : '☠ CONFIRM KILL SWITCH'}
                  </button>
                </div>
              </div>
            )}

            {(isKilled || needsRecovery || (liveServiceSelected && lifecycle?.phase === 'stopped')) && (
              <div
                style={{
                  marginTop: 14,
                  padding: 12,
                  border: '1px solid var(--red)',
                  borderRadius: 10,
                  background: 'rgba(239,68,68,.08)',
                  color: 'var(--red)',
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                {liveShutdownMessage(lifecycle)}
                {!!lifecycle?.unresolved_requests.length && (
                  <ul style={{ marginTop: 8 }}>
                    {lifecycle.unresolved_requests.map((request) => (
                      <li key={request.order_id}>
                        {request.symbol} · {request.purpose} · {request.status} · {request.reason}
                      </li>
                    ))}
                  </ul>
                )}
                {!!lifecycle?.unmanaged_symbols.length && (
                  <div>Unmanaged exposure: {lifecycle.unmanaged_symbols.join(', ')}</div>
                )}
              </div>
            )}

            {/* Telemetry strip. Replaces the prior 4-tile grid — same data,
                ~75% less vertical real estate, no SaaS-grid anti-pattern.
                Mono uppercase pairs (LABEL value) separated by middots. */}
            <div
              className="mono"
              style={{
                marginTop: 14,
                paddingTop: 14,
                borderTop: '1px solid var(--border-soft)',
                display: 'flex',
                gap: 16,
                flexWrap: 'wrap',
                alignItems: 'baseline',
                fontSize: 10,
                letterSpacing: '.18em',
                textTransform: 'uppercase',
                color: 'var(--fg-4)',
              }}
            >
              <span>
                Uptime{' '}
                <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
                  {fmtDuration(status.uptime_seconds || 0)}
                </strong>
              </span>
              <span style={{ opacity: 0.3 }}>·</span>
              <span>
                Next Scan{' '}
                <strong
                  style={{
                    color: isRunning ? 'var(--amber)' : 'var(--fg-3)',
                    fontWeight: 800,
                  }}
                >
                  {isRunning && status.next_scan_in_seconds != null
                    ? fmtDuration(Math.round(status.next_scan_in_seconds))
                    : '—'}
                </strong>
              </span>
              <span style={{ opacity: 0.3 }}>·</span>
              <span>
                Regime{' '}
                <strong style={{ color: 'var(--blue)', fontWeight: 800 }}>
                  {regime && regime.composite !== 'unknown'
                    ? regime.composite.replace(/_/g, ' ').toUpperCase()
                    : '—'}
                </strong>
              </span>
              <span style={{ opacity: 0.3 }}>·</span>
              <span>
                Min Score{' '}
                <strong style={{ color: 'var(--fg)', fontWeight: 800 }}>
                  {cfg?.min_confluence != null ? `≥${cfg.min_confluence}` : 'AUTO'}
                </strong>
              </span>
              {status.session_id && (
                <>
                  <span style={{ opacity: 0.3 }}>·</span>
                  <span>
                    Session{' '}
                    <strong style={{ color: 'var(--fg-3)', fontWeight: 800 }}>
                      {status.session_id.slice(0, 8)}
                    </strong>
                  </span>
                </>
              )}
            </div>

            {/* Config pills (when present) */}
            {cfg && (
              <div
                style={{
                  display: 'flex',
                  gap: 6,
                  flexWrap: 'wrap',
                  marginTop: 14,
                  paddingTop: 12,
                  borderTop: '1px solid var(--border-soft)',
                }}
              >
                {cfg.sniper_mode && <Chip>{cfg.sniper_mode.toUpperCase()}</Chip>}
                {cfg.duration_hours != null && <Chip>{cfg.duration_hours}H</Chip>}
                {cfg.max_positions != null && <Chip>{cfg.max_positions} SLOTS</Chip>}
                {cfg.risk_per_trade != null && <Chip>{cfg.risk_per_trade}% RISK</Chip>}
                {cfg.leverage != null && cfg.leverage !== 1 && (
                  <Chip>{cfg.leverage}× LEVERAGE</Chip>
                )}
              </div>
            )}
          </section>

          {/* Analyze output */}
          {(analyzeOutput || analyzeError) && (
            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="Analyze Session" />
              {analyzeError && (
                <div style={{ color: 'var(--red)', fontSize: 11, marginBottom: 8 }}>
                  ⚠ {analyzeError}
                </div>
              )}
              {analyzeOutput && (
                <pre
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--fg-2)',
                    whiteSpace: 'pre-wrap',
                    margin: 0,
                  }}
                >
                  {analyzeOutput}
                </pre>
              )}
            </section>
          )}

          <BotPositions positions={positions} pendingOrders={pendingOrders} onSelect={setDetailSelection} />

          <details className="session-diagnostics"><summary>Session statistics and diagnostic evidence</summary><CycleHeartbeat /><MacroBand />
          {/* ── Two-column: Equity + Statistics ──────────────────── */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 14,
            }}
          >
            <section className="panel" style={{ padding: 14 }}>
              <SectionHead
                title="Equity Curve"
                right={
                  <span
                    className="mono"
                    style={{ fontSize: 10, color: 'var(--fg-4)' }}
                  >
                    {trades.length} trades
                  </span>
                }
              />
              {tradesError && (
                <div style={{ color: 'var(--amber)', fontSize: 10, marginBottom: 6 }}>
                  ⚠ {tradesError}
                </div>
              )}
              <div className="mono" style={{ color: 'var(--fg-3)', fontSize: 11 }}>
                {accountingLabel(status?.accounting)}
                {status?.outcome_basis === 'executions_excluding_funding_and_transfers' && (
                  <div>Trade results include execution fees; funding and transfers are excluded.</div>
                )}
                {executionReportNotice(status?.execution_reporting, status?.execution_history) && (
                  <div role="status" style={{ color: 'var(--amber)' }}>
                    {executionReportNotice(status?.execution_reporting, status?.execution_history)}
                  </div>
                )}
                {status?.accounting?.basis === 'exchange_mark' && <div>Account change includes funding and transfers.{status?.outcome_basis !== 'executions_excluding_funding_and_transfers' && ' Trade outcomes are estimates.'}</div>}
              </div>
              {status?.accounting?.basis !== 'exchange_mark' && initialBalance != null && <EquitySparkline trades={trades} initialBalance={initialBalance} />}
              <div
                className="mono"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 10,
                  color: 'var(--fg-4)',
                  marginTop: 8,
                  textTransform: 'uppercase',
                  letterSpacing: '.14em',
                }}
              >
                <span>start {fmtCurrency(initialBalance)}</span>
                <span>now {fmtCurrency(balance?.equity)}</span>
                <span
                  style={{
                    color:
                      accountingColor(balance?.pnl),
                  }}
                >
                  {fmtCurrency(balance?.pnl)} ({fmtPct(balance?.pnl_pct)})
                </span>
              </div>
            </section>

            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="Statistics" />
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 10,
                }}
              >
                <MetricTile
                  label="Total PnL"
                  value={fmtCurrency(stats?.total_pnl ?? 0)}
                  sub={
                    stats?.total_pnl_pct != null
                      ? `${fmtPct(stats.total_pnl_pct)} realised`
                      : 'realised'
                  }
                  accent={
                    (stats?.total_pnl ?? 0) > 0
                      ? 'green'
                      : (stats?.total_pnl ?? 0) < 0
                        ? 'red'
                        : undefined
                  }
                />
                <MetricTile
                  label="Trades"
                  value={String(stats?.total_trades ?? 0)}
                  sub={`${stats?.winning_trades ?? 0}W / ${stats?.losing_trades ?? 0}L`}
                />
                <MetricTile
                  label="Win Rate"
                  value={
                    stats?.win_rate != null
                      ? `${stats.win_rate.toFixed(0)}%`
                      : '—'
                  }
                  sub="of closed"
                  accent={
                    stats && stats.win_rate >= 50 ? 'green' : undefined
                  }
                />
                <MetricTile
                  label="Avg R:R"
                  value={
                    stats?.avg_rr != null ? `${stats.avg_rr.toFixed(2)}R` : '—'
                  }
                  sub="realised"
                />
                <MetricTile
                  label="Best"
                  value={fmtCurrency(stats?.best_trade ?? 0)}
                  accent="green"
                />
                <MetricTile
                  label="Worst"
                  value={fmtCurrency(stats?.worst_trade ?? 0)}
                  accent="red"
                />
                <MetricTile
                  label="Max DD"
                  value={
                    stats?.max_drawdown != null
                      ? fmtPct(stats.max_drawdown)
                      : '—'
                  }
                  accent="amber"
                />
              </div>
            </section>
          </div>

          </details>
          {/* ── Signal Log ────────────────────────────────────────── */}
          <section className="panel" style={{ padding: 14 }}>
            <SectionHead
              title="Signal Log"
              right={
                <span
                  className="mono"
                  style={{ fontSize: 10, color: 'var(--fg-4)' }}
                >
                  {signalLog.length} entries
                </span>
              }
            />
            {signalLog.length === 0 ? (
              <div
                className="mono"
                style={{
                  padding: 18,
                  textAlign: 'center',
                  fontSize: 11,
                  color: 'var(--fg-4)',
                  letterSpacing: '.16em',
                  textTransform: 'uppercase',
                }}
              >
                — signal log empty —
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 6 }}>
                {signalLog.slice(0, 10).map((entry, i) => {
                  const ok = entry.result === 'executed';
                  const filtered = entry.result === 'filtered';
                  return (
                    <div
                      key={`${entry.symbol}-${i}`}
                      className="mono"
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '90px 1fr 80px',
                        gap: 8,
                        padding: '6px 8px',
                        fontSize: 11,
                        borderBottom: '1px solid var(--border-soft)',
                      }}
                    >
                      <span style={{ fontWeight: 700 }}>{entry.symbol}</span>
                      <span style={{ color: 'var(--fg-3)' }}>
                        {entry.reason || entry.setup_type || '—'}
                      </span>
                      <span
                        style={{
                          textAlign: 'right',
                          color: ok
                            ? 'var(--green)'
                            : filtered
                              ? 'var(--red)'
                              : 'var(--fg-4)',
                        }}
                      >
                        {ok ? '✓ exec' : filtered ? '✗ filter' : '⚠ err'}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* ── Gauntlet Breakdown — Phase 3g.ii.b ─────────────────── */}
          {/* Per-row click opens the PipelineTracer drawer (3g.ii.c).   */}
          <GauntletBreakdown
            signals={signalLog}
            onSignalClick={(id) => setTracerSignalId(id)}
            scannerModes={scannerModes}
            currentModeName={selectedMode?.name ?? null}
          />

          {/* ── Confluence Distribution — Phase 3g.ii.d ───────────── */}
          <ConfluenceBreakdown />

          {/* ── Deferred surfaces row ────────────────────────────── */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 14,
            }}
          >
            <UniversePanel />
            <section className="panel" style={{ padding: 14 }}>
              <SectionHead title="Diagnose" />
              <div style={{ padding: '10px 4px 4px' }}>
                <div
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--fg-3)',
                    letterSpacing: '.10em',
                    marginBottom: 10,
                  }}
                >
                  9-step playbook orchestrating phemex / universe / cycles /
                  signals_per_stage / fills checks. Failed steps deep-link
                  to the right tuning surface.
                </div>
                <button
                  type="button"
                  className="btn"
                  disabled={isPaper}
                  onClick={() => {
                    if (isPaper) return;
                    setDiagnoseOpenedAtMs(Date.now());
                    setDiagnoseOpen(true);
                  }}
                  style={{ width: '100%', fontSize: 10, letterSpacing: '.16em' }}
                >
                  {isPaper ? 'Live diagnostics unavailable for paper' : 'Inspect live executor and scanner'}
                </button>
              </div>
            </section>
          </div>
        </div>
      )}

      <FooterStatus />

      {/* PipelineTracer drawer — Phase 3g.ii.c. Renders only when a
          signal id is selected via Gauntlet detail row click. */}
      <PipelineTracer
        signalId={tracerSignalId}
        onClose={() => setTracerSignalId(null)}
      />

      {/* DiagnoseWizard — Phase 3g.ii.f. 9-step playbook modal. nowSec
          is captured at modal open time (Date.now() snapshot in the click
          handler) so stale-cycle checks use a fresh reference each time;
          the wizard's effect re-fetches all three observability endpoints
          each time `open` flips true. */}
      <DiagnoseWizard
        open={diagnoseOpen && !isPaper}
        onClose={() => setDiagnoseOpen(false)}
        status={liveStatus}
        nowSec={diagnoseOpenedAtMs / 1000}
      />

      {/* Active-trade detail modal. Renders the click-through chart +
          metadata for either a filled position or a pending limit. Pass
          the current regime composite as additional context when live;
          paper sessions don't expose regime in status. */}
      <PositionDetailModal
        selection={detailSelection}
        onClose={() => setDetailSelection(null)}
        currentRegime={regime?.composite ?? null}
      />
    </div>
  );
}

export default BotStatus;

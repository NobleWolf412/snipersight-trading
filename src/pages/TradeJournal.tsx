import { JournalFilterControls } from './JournalFilters';
import type { JournalFilters } from '@/services/tradeJournalService';
/**
 * TradeJournal — Phase 3b sub-step 1
 *
 * HUD chrome rewrite of the closed-trade analytics page. Path B:
 * keep ALL backend wiring (tradeJournalService, mlService, filters,
 * sort, CSV export, loading/error states); replace ONLY the visual
 * shell with the prototype/journal.jsx HUD design.
 *
 * What's NEW vs prior shadcn version:
 *   - Equity + drawdown dual-curve SVG (drawdown computed client-side
 *     from aggregate.equity_curve — backend doesn't ship it).
 *   - PnL Calendar (daily heatmap, computed client-side from trades).
 *   - Per-symbol / per-type breakdown as bar-style cards (not table).
 *   - Stat tiles in 8-wide grid; profit factor + expectancy computed
 *     client-side from aggregate fields.
 *
 * What's DEFERRED (backend lacks fields, will land in 3b sub-step 2):
 *   - Tag cloud — JournalTrade has no `tags`.
 *   - MFE-vs-R distribution scatter — no `rr` per trade.
 *   - Trade detail modal with notes — notes aren't persisted backend-side.
 *
 * MLPanel is the ML-gate boundary: visual restyled, behavior identical
 * (train / reset / clear / SHAP feature importance) — per "no live capital
 * before auth" the ML signal-quality gate must NOT regress.
 *
 * body[data-snapshot-ready="true"] is set after first successful load so
 * the visual capture framework knows when to capture.
 */
import {
Chip,
FooterStatus,
PageHead,
Reticle,
SectionHead,
TradeHistoryDetailModal,
fmtMoney,
} from '@/components/hud';
import {
tradeJournalService,
type JournalAggregate,
type JournalTrade
} from '@/services/tradeJournalService';
import { useEffect,useMemo,useRef,useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EXIT_REASON_LABELS,EquityCurve,GroupBreakdown,PnLCalendar,StatTile,fmt,fmtDate,type GroupRow } from './TradeJournalViews';

// ─── helpers ──────────────────────────────────────────────────────────────

// ─── Main page ────────────────────────────────────────────────────────────

type SortKey = 'exit_time' | 'symbol' | 'pnl' | 'trade_type' | 'exit_reason';
type SortDir = 'asc' | 'desc';

const INITIAL_EQUITY = 0; // This chart is realized P/L, not account equity.

export function TradeJournal() {
  const navigate = useNavigate();

  const [trades, setTrades] = useState<JournalTrade[]>([]);
  const [aggregate, setAggregate] = useState<JournalAggregate | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<JournalFilters>({ limit: 200 });
  const [symbolInput, setSymbolInput] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [exitFilter, setExitFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Sort
  const [sortKey, setSortKey] = useState<SortKey>('exit_time');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Group toggle for breakdown
  const [groupBy, setGroupBy] = useState<'symbol' | 'type'>('symbol');

  // Trade detail modal — set when the operator clicks a row in the log.
  const [selectedTrade, setSelectedTrade] = useState<JournalTrade | null>(null);

  const requestVersion = useRef(0);
  const load = async (f: JournalFilters) => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError(null);
    try {
      const data = await tradeJournalService.getJournal(f);
      if (version !== requestVersion.current) return;
      setTrades(data.trades);
      setAggregate(data.aggregate);
      setTotal(data.total);
    } catch {
      if (version !== requestVersion.current) return;
      // 3b.2: explicit copy distinguishing backend-offline from
      // backend-online-but-no-trades. The empty-state branch below
      // covers the latter (no error, sorted.length === 0). This
      // catch branch fires when the fetch itself fails — service
      // unreachable, network error, malformed response.
      setError('Journal could not be loaded. Retry to reconnect; prior records remain on disk.');
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  };

  useEffect(() => {
    load(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Snapshot-ready flag — set after first load resolves (success or error).
  useEffect(() => {
    if (!loading) {
      document.body.setAttribute('data-snapshot-ready', 'true');
    }
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, [loading]);

  const applyFilters = () => {
    const f: JournalFilters = {
      limit: 200,
      symbol: symbolInput || undefined,
      trade_type: typeFilter || undefined,
      exit_reason: exitFilter || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    };
    setFilters(f);
    load(f);
  };

  const resetFilters = () => {
    setSymbolInput('');
    setTypeFilter('');
    setExitFilter('');
    setStartDate('');
    setEndDate('');
    const f: JournalFilters = { limit: 200 };
    setFilters(f);
    load(f);
  };

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    return [...trades].sort((a, b) => {
      let av: string | number = a[sortKey] ?? '';
      let bv: string | number = b[sortKey] ?? '';
      if (sortKey === 'pnl') {
        av = a.pnl;
        bv = b.pnl;
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [trades, sortKey, sortDir]);

  const symbolRows = useMemo<GroupRow[]>(() => {
    if (!aggregate) return [];
    return Object.entries(aggregate.by_symbol)
      .map(([label, v]) => ({ label, ...v }))
      .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl));
  }, [aggregate]);

  const typeRows = useMemo<GroupRow[]>(() => {
    if (!aggregate) return [];
    return Object.entries(aggregate.by_type)
      .map(([label, v]) => ({ label: label.toUpperCase(), ...v }))
      .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl));
  }, [aggregate]);

  // Computed stats (profit factor + expectancy not in aggregate envelope)
  const profitFactor = useMemo(() => {
    if (!aggregate) return 0;
    const winsTotal = aggregate.avg_win * aggregate.winning_trades;
    const lossTotal = Math.abs(aggregate.avg_loss) * aggregate.losing_trades;
    return lossTotal > 0 ? winsTotal / lossTotal : Infinity;
  }, [aggregate]);

  const expectancy = useMemo(() => {
    if (!aggregate) return 0;
    const wr = aggregate.win_rate / 100;
    return wr * aggregate.avg_win - (1 - wr) * Math.abs(aggregate.avg_loss);
  }, [aggregate]);

  return (
    // 3b.2: `journal-page` class is the hook for Phase 3b.2 mobile rules
    // in hud.css. Class name remains `shell` for outer layout; we add
    // journal-page alongside so per-page CSS scoping works without
    // disrupting the existing shell padding cascade.
    <div className="shell journal-page">
      <PageHead
        icon={
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <rect
              x="4"
              y="3"
              width="14"
              height="18"
              rx="1.5"
              stroke="var(--green)"
              strokeWidth="1.7"
            />
            <line x1="8" y1="7" x2="14" y2="7" stroke="var(--green)" strokeWidth="1.5" />
            <line x1="8" y1="11" x2="14" y2="11" stroke="var(--green)" strokeWidth="1.5" />
            <line x1="8" y1="15" x2="11" y2="15" stroke="var(--green)" strokeWidth="1.5" />
            <circle cx="20" cy="20" r="3" stroke="var(--accent)" strokeWidth="1.4" />
            <line x1="22" y1="22" x2="24" y2="24" stroke="var(--accent)" strokeWidth="1.4" />
          </svg>
        }
        title="Journal"
        subtitle={`${total} closed trades · all sessions`}
        badges={
          <>
            {aggregate && (
              <>
                <Chip kind={aggregate.total_pnl >= 0 ? 'green' : 'red'}>
                  NET {aggregate.total_pnl >= 0 ? '+' : ''}
                  {fmtMoney(aggregate.total_pnl)}
                </Chip>
                <Chip kind="green">WR {aggregate.win_rate.toFixed(0)}%</Chip>
                <Chip kind="accent">PF {profitFactor.toFixed(2)}</Chip>
              </>
            )}
            <button
              className="btn"
              style={{ padding: '4px 10px', fontSize: 10 }}
              onClick={() =>
                window.open(tradeJournalService.getExportUrl(filters), '_blank')
              }
            >
              EXPORT CSV
            </button>
          </>
        }
      />

      {error && (
        <div
          style={{
            border: '1px solid rgba(248,113,113,.3)',
            background: 'rgba(248,113,113,.08)',
            color: 'var(--red-2)',
            padding: '10px 14px',
            borderRadius: 6,
            fontFamily: 'JetBrains Mono,monospace',
            fontSize: 12,
            marginBottom: 18,
          }}
        >
          {error}
        </div>
      )}

      {/* Two-column layout: trade log + breakdowns */}
      <div className="layout-grid">
        {/* Left col: trade log + calendar */}
        <div className="col">
          <section className="panel">
            <SectionHead
              title={
                <>
                  Trade Log <span style={{ color: 'var(--accent)' }}>{sorted.length}</span>
                </>
              }
              right={
                <Chip kind="accent">
                  SORT · {sortKey.toUpperCase()} {sortDir === 'desc' ? '↓' : '↑'}
                </Chip>
              }
            />
            <JournalFilterControls symbolInput={symbolInput} typeFilter={typeFilter} exitFilter={exitFilter} startDate={startDate} endDate={endDate} setSymbolInput={setSymbolInput} setTypeFilter={setTypeFilter} setExitFilter={setExitFilter} setStartDate={setStartDate} setEndDate={setEndDate} applyFilters={applyFilters} resetFilters={resetFilters} />
            <label className="journal-sort-control">Sort this page <select value={sortKey} onChange={e=>setSortKey(e.target.value as SortKey)}>{(['exit_time','symbol','pnl','trade_type','exit_reason'] as const).map(key=><option key={key} value={key}>{key.replace('_',' ')}</option>)}</select></label><button className="btn" onClick={()=>setSortDir(value=>value==='asc'?'desc':'asc')}>Order: {sortDir==='asc'?'ascending':'descending'}</button>
            <div className="journal-pagination">
              <button className="btn" disabled={loading || !(filters.offset ?? 0)} onClick={() => {
                const f = { ...filters, offset: Math.max(0, (filters.offset ?? 0) - 200) }; setFilters(f); void load(f);
              }}>Previous</button>
              <span>{total ? (filters.offset ?? 0) + 1 : 0}–{Math.min((filters.offset ?? 0) + trades.length, total)} of {total} matching trades · sorting and calendar cover this page</span>
              <button className="btn" disabled={loading || (filters.offset ?? 0) + trades.length >= total} onClick={() => {
                const f = { ...filters, offset: (filters.offset ?? 0) + 200 }; setFilters(f); void load(f);
              }}>Next</button>
              <button className="btn" disabled={loading} onClick={() => void load(filters)}>Refresh</button>
            </div>
            <div style={{ maxHeight: 520, overflowY: 'auto' }}>
              <div
                className="journal-trade-header"
                style={{
                  position: 'sticky',
                  top: 0,
                  background: 'var(--card)',
                  zIndex: 1,
                  borderBottom: '1px solid var(--border-soft)',
                }}
              >
                <button type="button" className="journal-sort" onClick={() => toggleSort('exit_time')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'exit_time' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  TIME
                  {sortKey === 'exit_time' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </button>
                <button type="button" className="journal-sort" onClick={() => toggleSort('symbol')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'symbol' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  SYMBOL
                  {sortKey === 'symbol' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </button>
                <span>DIR</span>
                <button type="button" className="journal-sort" onClick={() => toggleSort('trade_type')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'trade_type' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  TYPE
                  {sortKey === 'trade_type' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </button>
                <button type="button" className="journal-sort" onClick={() => toggleSort('pnl')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'pnl' ? 'var(--accent)' : 'var(--fg-4)',
                  }}
                >
                  P&amp;L
                  {sortKey === 'pnl' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </button>
                <span>MFE</span>
                <span>MAE</span>
                <button type="button" className="journal-sort" onClick={() => toggleSort('exit_reason')}
                  style={{
                    cursor: 'pointer',
                    color: sortKey === 'exit_reason' ? 'var(--accent)' : 'var(--fg-4)',
                    textAlign: 'right',
                  }}
                >
                  EXIT
                  {sortKey === 'exit_reason' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </button>
              </div>
              {loading ? (
                <div
                  style={{
                    padding: '36px 18px',
                    textAlign: 'center',
                    color: 'var(--fg-4)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                  }}
                >
                  // loading journal…
                </div>
              ) : sorted.length === 0 ? (
                <div
                  style={{
                    padding: '36px 18px',
                    textAlign: 'center',
                    color: 'var(--fg-4)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                  }}
                >
                  {/* 3b.2: empty-state copy differs from the catch-branch
                      banner above. Here the fetch succeeded but there
                      are zero closed trades to show — operator needs
                      to be told what's missing AND how to generate
                      data (run paper bot or live bot to closure). */}
                  {total === 0 ? (
                    <>// no closed trades yet · run the paper bot to start logging</>
                  ) : (
                    <>// no trades match the current filters · clear or relax filter set</>
                  )}
                </div>
              ) : (
                sorted.map(tr => {
                  const profit = tr.pnl >= 0;
                  return (
                    <div
                      key={tr.trade_id}
                      className="journal-trade-row"
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedTrade(tr)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedTrade(tr);
                        }
                      }}
                      aria-label={`Inspect ${tr.symbol} ${tr.direction} ${tr.trade_type} trade, net P&L ${fmtMoney(tr.pnl)}, exit ${tr.exit_reason}`}
                      style={{ cursor: 'pointer' }}
                    >
                      <span data-label="Time" style={{ color: 'var(--fg-3)' }}>{fmtDate(tr.exit_time)}</span>
                      <span data-label="Symbol"
                        style={{
                          color: 'var(--fg)',
                          fontWeight: 600,
                          letterSpacing: '.04em',
                        }}
                      >
                        {tr.symbol}
                      </span>
                      <span data-label="Direction"
                        style={{
                          color:
                            tr.direction === 'LONG' ? 'var(--green-soft)' : 'var(--red-2)',
                          fontWeight: 700,
                        }}
                      >
                        {tr.direction === 'LONG' ? '▲L' : '▼S'}
                      </span>
                      <span data-label="Trade type" style={{ color: 'var(--fg-2)', fontSize: 10 }}>
                        {tr.trade_type.toUpperCase()}
                      </span>
                      <span data-label="Net P&L"
                        style={{
                          color: profit ? 'var(--green-soft)' : 'var(--red-2)',
                          fontWeight: 800,
                        }}
                      >
                        {(profit ? '+' : '') + fmtMoney(tr.pnl)}
                        <span
                          style={{
                            fontSize: 9,
                            marginLeft: 4,
                            fontWeight: 500,
                          }}
                        >
                          ({fmt(tr.pnl_pct, 2)}%)
                        </span>
                      </span>
                      <span data-label="MFE" style={{ color: 'var(--green-soft)' }}>
                        +{fmt(tr.max_favorable, 1)}
                      </span>
                      <span data-label="MAE" style={{ color: 'var(--red-2)' }}>
                        -{fmt(tr.max_adverse, 1)}
                      </span>
                      <span data-label="Exit"
                        style={{
                          color: 'var(--fg-4)',
                          fontSize: 9,
                          textAlign: 'right',
                          letterSpacing: '.1em',
                        }}
                      >
                        {EXIT_REASON_LABELS[tr.exit_reason] ?? tr.exit_reason.toUpperCase()}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </section>

          <section className="panel">
            <SectionHead title="P&L Calendar" right={<Chip>DAILY</Chip>} />
            <div style={{ padding: '14px 18px' }}>
              <PnLCalendar trades={trades} />
            </div>
          </section>
        </div>

        {/* Right col: breakdowns + ML */}
        <div className="col">
          <section className="panel">
            <SectionHead
              title={`Per-${groupBy === 'symbol' ? 'Symbol' : 'Type'} Breakdown`}
              right={
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    className={`btn ${groupBy === 'symbol' ? 'btn-cyan' : ''}`}
                    style={{ padding: '4px 10px', fontSize: 10 }}
                    onClick={() => setGroupBy('symbol')}
                  >
                    SYMBOL
                  </button>
                  <button
                    className={`btn ${groupBy === 'type' ? 'btn-cyan' : ''}`}
                    style={{ padding: '4px 10px', fontSize: 10 }}
                    onClick={() => setGroupBy('type')}
                  >
                    TYPE
                  </button>
                </div>
              }
            />
            <div style={{ padding: '14px 18px' }}>
              <GroupBreakdown rows={groupBy === 'symbol' ? symbolRows : typeRows} />
            </div>
          </section>

        </div>
      </div>

      {/* Stats command center */}
      {aggregate && (
        <section className="panel panel-accent" style={{ marginBottom: 18 }}>
          <Reticle />
          <div className="corner-tag tl">// PERFORMANCE-METRICS</div>
          <div className="corner-tag tr">ALL-SESSIONS WINDOW</div>
          <div style={{ padding: '22px 22px 18px' }}>
            <div className="journal-stat-grid">
              <StatTile
                label="Net P&L"
                value={
                  (aggregate.total_pnl >= 0 ? '+' : '') + fmtMoney(aggregate.total_pnl)
                }
                sub="across all closed"
                color={aggregate.total_pnl >= 0 ? 'var(--green-soft)' : 'var(--red-2)'}
                big
              />
              <StatTile
                label="Win Rate"
                value={aggregate.win_rate.toFixed(1) + '%'}
                sub={`${aggregate.winning_trades} / ${aggregate.total_trades}`}
                color="var(--green-soft)"
                big
              />
              <StatTile
                label="Profit Fctr"
                value={Number.isFinite(profitFactor) ? profitFactor.toFixed(2) : '∞'}
                sub={
                  profitFactor > 1.5 ? 'healthy' : profitFactor > 1 ? 'thin' : 'losing'
                }
                color={
                  profitFactor > 1.5
                    ? 'var(--green-soft)'
                    : profitFactor > 1
                    ? 'var(--amber)'
                    : 'var(--red-2)'
                }
                big
              />
              <StatTile
                label="Avg R"
                value={(aggregate.avg_rr >= 0 ? '+' : '') + aggregate.avg_rr.toFixed(2) + 'R'}
                sub="per trade"
                color={aggregate.avg_rr >= 0 ? 'var(--green-soft)' : 'var(--red-2)'}
                big
              />
              <StatTile
                label="Expectancy"
                value={(expectancy >= 0 ? '+' : '') + fmtMoney(expectancy)}
                sub="per trade EV"
                color={expectancy >= 0 ? 'var(--green-soft)' : 'var(--red-2)'}
                big
              />
              <StatTile
                label="Avg Win"
                value={'+' + fmtMoney(aggregate.avg_win)}
                sub={`${aggregate.winning_trades} wins`}
                color="var(--green-soft)"
              />
              <StatTile
                label="Avg Loss"
                value={fmtMoney(aggregate.avg_loss)}
                sub={`${aggregate.losing_trades} losses`}
                color="var(--red-2)"
              />
              <StatTile
                label="Max DD"
                value={fmtMoney(aggregate.max_drawdown)}
                sub="peak-to-trough"
                color="var(--red-2)"
              />
            </div>

            <div
              style={{ paddingTop: 14, borderTop: '1px solid var(--border-soft)' }}
            >
              <div
                className="mono"
                style={{
                  fontSize: 10,
                  color: 'var(--fg-4)',
                  letterSpacing: '.20em',
                  textTransform: 'uppercase',
                  marginBottom: 10,
                }}
              >
                // CUMULATIVE REALIZED P/L · DRAWDOWN ($) · ALL SESSIONS
              </div>
              {aggregate.equity_curve.length > 1 ? (
                <EquityCurve
                  equityCurve={aggregate.equity_curve}
                  initial={INITIAL_EQUITY}
                />
              ) : (
                <div
                  className="mono"
                  style={{ fontSize: 11, color: 'var(--fg-4)' }}
                >
                  // not enough closed trades for realized P/L curve
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      <FooterStatus />

      {/* Closed-trade post-mortem chart. Renders when a Trade Log row is
          clicked. Shows the trade's symbol on a TF inferred from
          trade_type with entry/exit price lines + entry/exit candle
          markers so the operator can see why the trade went the way it
          went. */}
      <TradeHistoryDetailModal
        trade={selectedTrade}
        onClose={() => setSelectedTrade(null)}
      />
    </div>
  );
}

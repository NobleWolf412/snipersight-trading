import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { ArrowUp, ArrowDown, Download, Funnel, ArrowClockwise, Brain, SpinnerGap } from '@phosphor-icons/react';
import { PageShell } from '@/components/layout/PageShell';
import { HomeButton } from '@/components/layout/HomeButton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  tradeJournalService,
  type JournalTrade,
  type JournalAggregate,
  type JournalFilters,
} from '@/services/tradeJournalService';
import { mlService, type MLStatus, type FeatureImportanceItem } from '@/services/mlService';

// ─── helpers ──────────────────────────────────────────────────────────────────

function fmt(n: number, decimals = 2) {
  return n.toFixed(decimals);
}

function fmtDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function pnlColor(n: number) {
  return n > 0 ? 'text-green-400' : n < 0 ? 'text-red-400' : 'text-muted-foreground';
}

const EXIT_REASON_LABELS: Record<string, string> = {
  target: 'Target',
  stop_loss: 'Stop',
  stagnation: 'Stale',
  manual: 'Manual',
  max_hours: 'Timeout',
};

// ─── StatCard ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="border-border/40 bg-card/60 backdrop-blur-sm">
      <CardContent className="pt-4 pb-3">
        <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest mb-1">{label}</p>
        <p className="text-2xl font-bold heading-hud">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </CardContent>
    </Card>
  );
}

// ─── BreakdownTable ────────────────────────────────────────────────────────────

function BreakdownTable({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; trades: number; wins: number; pnl: number; win_rate: number }[];
}) {
  return (
    <Card className="border-border/40 bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm heading-hud text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/30 text-muted-foreground text-xs font-mono">
              <th className="text-left px-4 py-2">SYMBOL</th>
              <th className="text-right px-3 py-2">TRADES</th>
              <th className="text-right px-3 py-2">W%</th>
              <th className="text-right px-4 py-2">P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-border/20 hover:bg-card/80 transition-colors">
                <td className="px-4 py-2 font-mono font-semibold">{r.label}</td>
                <td className="px-3 py-2 text-right text-muted-foreground">{r.trades}</td>
                <td className="px-3 py-2 text-right">
                  <span className={r.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}>
                    {fmt(r.win_rate, 1)}%
                  </span>
                </td>
                <td className={`px-4 py-2 text-right font-mono font-semibold ${pnlColor(r.pnl)}`}>
                  {r.pnl >= 0 ? '+' : ''}${fmt(r.pnl)}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground text-xs">
                  No data
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

// ─── MLPanel ──────────────────────────────────────────────────────────────────

function MLPanel() {
  const [status, setStatus] = useState<MLStatus | null>(null);
  const [importance, setImportance] = useState<FeatureImportanceItem[]>([]);
  const [training, setTraining] = useState(false);
  const [trainMsg, setTrainMsg] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);

  const fetchStatus = async () => {
    try {
      const s = await mlService.getStatus();
      setStatus(s);
      if (s.trained) {
        const feats = await mlService.getFeatureImportance();
        setImportance(feats.slice(0, 12));
      }
    } catch {
      // backend may not be running yet
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const handleTrain = async () => {
    setTraining(true);
    setTrainMsg(null);
    try {
      const result = await mlService.train();
      setTrainMsg(result.message);
      await fetchStatus();
    } catch (e: any) {
      setTrainMsg(e?.message ?? 'Training failed');
    } finally {
      setTraining(false);
    }
  };

  const accuracy = status?.accuracy ?? 0;
  const accuracyColor =
    accuracy >= 0.65 ? 'text-green-400' : accuracy >= 0.55 ? 'text-yellow-400' : 'text-red-400';

  return (
    <Card className="border-border/40 bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Brain size={16} className="text-primary" />
            <CardTitle className="text-sm heading-hud text-muted-foreground">EDGE MODEL</CardTitle>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="font-mono text-xs gap-2"
            disabled={training}
            onClick={handleTrain}
          >
            {training ? <SpinnerGap size={12} className="animate-spin" /> : <Brain size={12} />}
            {training ? 'TRAINING...' : 'TRAIN MODEL'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loadingStatus ? (
          <p className="text-xs text-muted-foreground font-mono animate-pulse">Loading model status...</p>
        ) : !status ? (
          <p className="text-xs text-muted-foreground font-mono">Backend not reachable.</p>
        ) : (
          <>
            {/* Status strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest mb-1">Status</p>
                <p className={`text-sm font-bold font-mono ${status.trained ? 'text-green-400' : 'text-muted-foreground'}`}>
                  {status.trained ? 'TRAINED' : 'UNTRAINED'}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest mb-1">Model</p>
                <p className="text-sm font-bold font-mono">{status.model_type === 'none' ? '—' : status.model_type}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest mb-1">Samples</p>
                <p className="text-sm font-bold font-mono">
                  {status.n_samples}
                  <span className="text-xs text-muted-foreground ml-1">/ {status.min_samples_required} min</span>
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest mb-1">CV Accuracy</p>
                <p className={`text-sm font-bold font-mono ${accuracyColor}`}>
                  {status.trained ? `${(accuracy * 100).toFixed(1)}%` : '—'}
                </p>
                {status.trained && (
                  <p className="text-[10px] text-muted-foreground font-mono mt-0.5">purged walk-fwd</p>
                )}
              </div>
            </div>

            {/* Insight callouts */}
            {!status.trained && (
              <div className="rounded-md border border-yellow-500/20 bg-yellow-500/5 px-3 py-2 text-xs font-mono text-yellow-400">
                Need {Math.max(0, status.min_samples_required - status.n_samples)} more enriched trade
                {Math.max(0, status.min_samples_required - status.n_samples) !== 1 ? 's' : ''} before training is possible.
              </div>
            )}
            {status.trained && accuracy < 0.55 && (
              <div className="rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs font-mono text-red-400">
                Accuracy below 55% — gather more diverse trades before relying on predictions.
              </div>
            )}
            {status.trained && accuracy >= 0.65 && (
              <div className="rounded-md border border-green-500/20 bg-green-500/5 px-3 py-2 text-xs font-mono text-green-400">
                Model looks solid. Green bars = conditions that help your win rate. Red = conditions that hurt it.
              </div>
            )}
            {status.trained && accuracy >= 0.55 && accuracy < 0.65 && (
              <div className="rounded-md border border-yellow-500/20 bg-yellow-500/5 px-3 py-2 text-xs font-mono text-yellow-400">
                Moderate accuracy — more trades will sharpen the model. Use feature directions as guidance only.
              </div>
            )}

            {trainMsg && (
              <p className="text-xs font-mono text-muted-foreground">{trainMsg}</p>
            )}

            {/* Feature importance chart — directional SHAP */}
            {importance.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest">
                    SHAP FEATURE IMPORTANCE
                  </p>
                  <div className="flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-2 h-2 rounded-sm bg-green-500" />
                      helps win rate
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-2 h-2 rounded-sm bg-red-500" />
                      hurts win rate
                    </span>
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    layout="vertical"
                    data={importance}
                    margin={{ top: 0, right: 12, left: 8, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 10, fill: '#888' }}
                      tickFormatter={(v) => v.toFixed(3)}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 10, fill: '#aaa', fontFamily: 'monospace' }}
                      width={148}
                    />
                    <Tooltip
                      contentStyle={{ background: '#0a0a0a', border: '1px solid #333', fontSize: 11 }}
                      formatter={(v: number, _name: string, props: any) => {
                        const dir = props?.payload?.direction ?? 0;
                        const dirLabel = dir > 0 ? '▲ helps win rate' : '▼ hurts win rate';
                        return [`${v.toFixed(5)}  ${dirLabel}`, 'SHAP |importance|'];
                      }}
                    />
                    <Bar dataKey="importance" radius={[0, 3, 3, 0]}>
                      {importance.map((item, i) => (
                        <Cell
                          key={i}
                          fill={item.direction >= 0 ? '#22c55e' : '#ef4444'}
                          opacity={0.7 + 0.3 * (1 - i / importance.length)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

type SortKey = 'exit_time' | 'symbol' | 'pnl' | 'trade_type' | 'exit_reason';
type SortDir = 'asc' | 'desc';

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

  const load = async (f: JournalFilters) => {
    setLoading(true);
    setError(null);
    try {
      const data = await tradeJournalService.getJournal(f);
      setTrades(data.trades);
      setAggregate(data.aggregate);
      setTotal(data.total);
    } catch (e) {
      setError('Could not load journal — is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(filters);
  }, []);

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
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    return [...trades].sort((a, b) => {
      let av: string | number = a[sortKey] ?? '';
      let bv: string | number = b[sortKey] ?? '';
      if (sortKey === 'pnl') { av = a.pnl; bv = b.pnl; }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [trades, sortKey, sortDir]);

  const symbolRows = useMemo(() => {
    if (!aggregate) return [];
    return Object.entries(aggregate.by_symbol)
      .map(([label, v]) => ({ label, ...v }))
      .sort((a, b) => b.trades - a.trades);
  }, [aggregate]);

  const typeRows = useMemo(() => {
    if (!aggregate) return [];
    return Object.entries(aggregate.by_type)
      .map(([label, v]) => ({ label, ...v }))
      .sort((a, b) => b.trades - a.trades);
  }, [aggregate]);

  const SortIcon = ({ k }: { k: SortKey }) =>
    sortKey === k ? (
      sortDir === 'asc' ? <ArrowUp size={10} className="inline ml-1" /> : <ArrowDown size={10} className="inline ml-1" />
    ) : null;

  return (
    <PageShell>
      <div className="space-y-8 pb-16">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-start gap-4">
            <HomeButton />
            <div>
              <h1 className="text-3xl font-bold heading-hud">TRADE JOURNAL</h1>
              <p className="text-sm text-muted-foreground mt-1 font-mono">
                {total} trades across all sessions
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="font-mono text-xs gap-2"
            onClick={() => window.open(tradeJournalService.getExportUrl(filters), '_blank')}
          >
            <Download size={14} />
            EXPORT CSV
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400 font-mono">
            {error}
          </div>
        )}

        {/* Stats strip */}
        {aggregate && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <StatCard label="Total Trades" value={String(aggregate.total_trades)} />
            <StatCard
              label="Win Rate"
              value={`${fmt(aggregate.win_rate, 1)}%`}
              sub={`${aggregate.winning_trades}W / ${aggregate.losing_trades}L`}
            />
            <StatCard
              label="Total P&L"
              value={`${aggregate.total_pnl >= 0 ? '+' : ''}$${fmt(aggregate.total_pnl)}`}
            />
            <StatCard label="Avg R:R" value={fmt(aggregate.avg_rr)} />
            <StatCard label="Avg Win" value={`$${fmt(aggregate.avg_win)}`} />
            <StatCard label="Avg Loss" value={`$${fmt(Math.abs(aggregate.avg_loss))}`} />
            <StatCard label="Max Drawdown" value={`$${fmt(aggregate.max_drawdown)}`} />
          </div>
        )}

        {/* Equity curve */}
        {aggregate && aggregate.equity_curve.length > 1 && (
          <Card className="border-border/40 bg-card/60 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm heading-hud text-muted-foreground">CUMULATIVE P&amp;L</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={aggregate.equity_curve} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 10, fill: '#888' }}
                    tickFormatter={(v) => fmtDate(v)}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#888' }}
                    tickFormatter={(v) => `$${v}`}
                    width={55}
                  />
                  <Tooltip
                    contentStyle={{ background: '#0a0a0a', border: '1px solid #333', fontSize: 12 }}
                    labelFormatter={(v) => fmtDate(v as string)}
                    formatter={(v: number) => [`$${fmt(v)}`, 'P&L']}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#22c55e"
                    strokeWidth={2}
                    fill="url(#pnlGradient)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Breakdowns */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <BreakdownTable title="BY SYMBOL" rows={symbolRows} />
          <BreakdownTable title="BY TRADE TYPE" rows={typeRows} />
        </div>

        {/* ML Panel */}
        <MLPanel />

        {/* Filters */}
        <Card className="border-border/40 bg-card/60 backdrop-blur-sm">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Funnel size={14} className="text-muted-foreground" />
              <CardTitle className="text-sm heading-hud text-muted-foreground">FILTERS</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <input
                className="col-span-1 bg-background/60 border border-border/40 rounded px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:border-primary/60"
                placeholder="Symbol (e.g. BTC/USDT)"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value.toUpperCase())}
              />
              <select
                className="bg-background/60 border border-border/40 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary/60"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
              >
                <option value="">All types</option>
                <option value="scalp">Scalp</option>
                <option value="intraday">Intraday</option>
                <option value="swing">Swing</option>
              </select>
              <select
                className="bg-background/60 border border-border/40 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary/60"
                value={exitFilter}
                onChange={(e) => setExitFilter(e.target.value)}
              >
                <option value="">All exits</option>
                <option value="target">Target</option>
                <option value="stop_loss">Stop loss</option>
                <option value="stagnation">Stagnation</option>
                <option value="manual">Manual</option>
              </select>
              <input
                type="date"
                className="bg-background/60 border border-border/40 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary/60"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
              <input
                type="date"
                className="bg-background/60 border border-border/40 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary/60"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="flex gap-2 mt-3">
              <Button size="sm" className="font-mono text-xs" onClick={applyFilters}>
                APPLY
              </Button>
              <Button size="sm" variant="ghost" className="font-mono text-xs gap-1" onClick={resetFilters}>
                <ArrowClockwise size={12} /> RESET
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Trade table */}
        <Card className="border-border/40 bg-card/60 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm heading-hud text-muted-foreground">
              TRADE HISTORY{' '}
              <span className="text-primary ml-2">{sorted.length}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            {loading ? (
              <div className="py-16 text-center text-muted-foreground text-sm font-mono animate-pulse">
                LOADING JOURNAL...
              </div>
            ) : sorted.length === 0 ? (
              <div className="py-16 text-center text-muted-foreground text-sm font-mono">
                No trades found. Start the bot and complete some trades.
              </div>
            ) : (
              <table className="w-full text-sm min-w-[720px]">
                <thead>
                  <tr className="border-b border-border/30 text-muted-foreground text-xs font-mono">
                    {(
                      [
                        ['exit_time', 'TIME'],
                        ['symbol', 'SYMBOL'],
                        ['trade_type', 'TYPE'],
                        ['exit_reason', 'EXIT'],
                        ['pnl', 'P&L'],
                      ] as [SortKey, string][]
                    ).map(([k, label]) => (
                      <th
                        key={k}
                        className="text-left px-4 py-3 cursor-pointer hover:text-foreground select-none"
                        onClick={() => toggleSort(k)}
                      >
                        {label}
                        <SortIcon k={k} />
                      </th>
                    ))}
                    <th className="text-right px-4 py-3">ENTRY</th>
                    <th className="text-right px-4 py-3">EXIT</th>
                    <th className="text-right px-4 py-3">MFE / MAE</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((t) => (
                    <tr
                      key={t.trade_id}
                      className="border-b border-border/20 hover:bg-card/80 transition-colors"
                    >
                      <td className="px-4 py-2.5 text-muted-foreground text-xs font-mono whitespace-nowrap">
                        {fmtDate(t.exit_time)}
                      </td>
                      <td className="px-4 py-2.5 font-mono font-semibold whitespace-nowrap">
                        <span className={t.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}>
                          {t.direction === 'LONG' ? '↑' : '↓'}
                        </span>{' '}
                        {t.symbol}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge
                          variant="outline"
                          className="text-xs font-mono border-border/40 capitalize"
                        >
                          {t.trade_type}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge
                          variant="outline"
                          className={`text-xs font-mono border-border/40 ${
                            t.exit_reason === 'target'
                              ? 'border-green-500/40 text-green-400'
                              : t.exit_reason === 'stop_loss'
                              ? 'border-red-500/40 text-red-400'
                              : ''
                          }`}
                        >
                          {EXIT_REASON_LABELS[t.exit_reason] ?? t.exit_reason}
                        </Badge>
                      </td>
                      <td className={`px-4 py-2.5 font-mono font-bold ${pnlColor(t.pnl)}`}>
                        {t.pnl >= 0 ? '+' : ''}${fmt(t.pnl)}
                        <span className="text-xs font-normal ml-1 opacity-60">
                          ({fmt(t.pnl_pct, 2)}%)
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs text-muted-foreground">
                        ${fmt(t.entry_price, 4)}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs text-muted-foreground">
                        ${fmt(t.exit_price, 4)}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs">
                        <span className="text-green-400">+${fmt(t.max_favorable, 2)}</span>
                        {' / '}
                        <span className="text-red-400">-${fmt(t.max_adverse, 2)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { ArrowUp, ArrowDown, Download, Funnel, ArrowClockwise } from '@phosphor-icons/react';
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

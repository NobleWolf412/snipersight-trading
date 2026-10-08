export interface AccountBalance {
  initial: number | null;
  current: number | null;
  equity: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  prices_age_seconds?: number | null;
}

export interface AccountingStatus {
  version: number;
  basis: 'exchange_mark' | 'simulation';
  state: 'ready' | 'unavailable' | 'unsupported' | 'stale' | 'reconciling';
  reasons: string[];
  entry_eligible: boolean;
  observation_valid: boolean;
  received_at: string | null;
  age_seconds: number | null;
  wallet: number | null;
  free: number | null;
  used: number | null;
  unrealized_pnl: number | null;
  equity: number | null;
}

export interface ExecutionReportState {
  state: 'pending' | 'published' | 'error';
  entry_order_id?: string;
  reasons?: string[];
}
export interface ExecutionHistoryStatus {
  reports?: ExecutionReportState[];
  report_error?: string | null;
}
export interface ExecutionOutcomeSnapshot {
  version: number;
  basis: 'executions_excluding_funding_and_transfers';
  complete: boolean;
  entry_order_id: string;
  exit_order_ids: string[];
  entry_quantity: string;
  exit_quantity: string;
  entry_cost: string | null;
  exit_cost: string | null;
  gross_pnl: string | null;
  fees: Record<string, string>;
  fees_complete: boolean;
  pnl_after_execution_fees: string | null;
  funding: null;
  funding_allocated: false;
  reasons: string[];
}

export function executionReportNotice(
  managed?: Record<string, ExecutionReportState>, history?: ExecutionHistoryStatus,
): string {
  const reports = new Map(Object.entries(managed ?? {}));
  for (const report of history?.reports ?? []) {
    if (!report.entry_order_id) continue;
    const previous = reports.get(report.entry_order_id);
    if (!previous || report.state === 'error' || previous.state !== 'error') {
      reports.set(report.entry_order_id, report);
    }
  }
  if (history?.report_error) return 'Trade reporting is unavailable; totals may be incomplete.';
  const errors = [...reports.values()].filter(r => r.state === 'error').length;
  if (errors) return `${errors} trade report${errors === 1 ? ' needs' : 's need'} review; totals may be incomplete.`;
  const pending = [...reports.values()].filter(r => r.state === 'pending').length;
  return pending ? `${pending} closed trade${pending === 1 ? ' awaits' : 's await'} accounting; completed totals exclude pending trades.` : '';
}

export function accountingLabel(status?: AccountingStatus): string {
  if (!status || status.basis === 'simulation') return 'Simulation equity';
  return `Exchange account equity · ${status.state}${status.entry_eligible ? '' : ' · new entries paused'}`;
}

export function formatAccountMoney(value: number | null | undefined, decimals = 2): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(value);
}

export function accountingColor(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value === 0) return 'var(--fg-4)';
  return value > 0 ? 'var(--green)' : 'var(--red)';
}

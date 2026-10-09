import { api, type ScannerMode } from '@/utils/api';
import { scanHistoryService } from './scanHistoryService';
import { convertSignalToScanResult } from '@/utils/mockData';

type Job = NonNullable<Awaited<ReturnType<typeof api.getScanRun>>['data']>;
type Params = Parameters<typeof api.createScanRun>[0];
export type ScanStatus = Job['status'] | 'idle' | 'starting' | 'disconnected' | 'cancelling';
export interface ScanProgress {
  status: ScanStatus; progress: number; total: number; currentSymbol: string | null;
  error: string | null; signalsFound: number; rejections: ReturnType<typeof summarizeRejections>;
  runId: string | null; startedAt: string | null; completedAt: string | null;
  autoScan: boolean; historyVersion: number;
}
const ACTIVE_KEY = 'sniper.scanner.active.v2';
const initial: ScanProgress = { status: 'idle', progress: 0, total: 0, currentSymbol: null,
  error: null, signalsFound: 0, rejections: null, runId: null, startedAt: null,
  completedAt: null, autoScan: false, historyVersion: 0 };
export const scanIsBusy = (status: ScanStatus) =>
  ['starting', 'queued', 'running', 'disconnected', 'cancelling'].includes(status);

export function summarizeRejections(raw: any) {
  if (!raw || typeof raw !== 'object') return null;
  const byReason = Object.entries(raw.by_reason ?? {})
    .filter(([reason, count]) => reason !== 'features' && typeof count === 'number' && count > 0)
    .map(([reason, count]) => ({ reason, count: count as number,
      examples: (Array.isArray(raw.details?.[reason]) ? raw.details[reason] : [])
        .slice(0, 3).map((d: any) => d?.symbol).filter((s: unknown): s is string => typeof s === 'string' && !!s),
    })).sort((a, b) => b.count - a.count);
  const total = typeof raw.total_rejected === 'number' ? raw.total_rejected : byReason.reduce((n, r) => n + r.count, 0);
  return total || byReason.length ? { total, byReason } : null;
}

/** One browser application owns a run across route changes. Failed polling never means a failed job. */
export class ScanRunService {
  private state: ScanProgress = { ...initial };
  private listeners = new Set<() => void>();
  private timer?: ReturnType<typeof setTimeout>;
  private polling = false;
  private initialized = false;
  private cancelRequested = false;
  private restoredCancellation = false;
  private cancelError: string | null = null;
  private creating = false;
  private acknowledged = true;
  private mode?: ScannerMode;
  private params?: Params;
  constructor(private client = api, private history = scanHistoryService,
    private storage: () => Storage = () => localStorage) {}
  getSnapshot = () => this.state;
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  private update(patch: Partial<ScanProgress>) { this.state = { ...this.state, ...patch }; this.listeners.forEach(fn => fn()); }
  private clearTimer() { if (this.timer) clearTimeout(this.timer); this.timer = undefined; }
  private schedule(fn: () => void, delay: number) { this.clearTimer(); this.timer = setTimeout(fn, delay); }
  resume = () => {
    if (this.initialized) return;
    this.initialized = true;
    try {
      const saved = JSON.parse(this.storage().getItem(ACTIVE_KEY) ?? 'null');
      if (typeof saved?.runId === 'string' && typeof saved?.mode?.name === 'string') {
        this.mode = saved.mode; this.params = saved.params;
        this.acknowledged = saved.acknowledged !== false;
        this.cancelRequested = saved.cancelRequested === true;
        this.restoredCancellation = this.cancelRequested;
        // Reload reconnects the existing job; automatic repeats require fresh opt-in.
        this.update({ runId: saved.runId, status: 'disconnected' });
        void this.poll();
      }
    } catch { this.update({ error: 'Saved scan could not be restored.' }); }
  };
  setAutoScan = (enabled: boolean) => {
    this.update({ autoScan: enabled });
    if (!enabled && !scanIsBusy(this.state.status)) this.clearTimer();
  };
  start = async (mode: ScannerMode, params: Params = {}) => {
    if (scanIsBusy(this.state.status)) return;
    this.clearTimer(); this.mode = { ...mode }; this.params = { ...params, sniper_mode: mode.name.toLowerCase(), request_id: crypto.randomUUID() };
    this.cancelRequested = false;
    this.restoredCancellation = false;
    this.cancelError = null;
    this.acknowledged = false;
    this.creating = true;
    this.update({ ...initial, autoScan: this.state.autoScan, historyVersion: this.state.historyVersion, status: 'starting', runId: this.params.request_id! });
    try {
      try { this.storage().setItem(ACTIVE_KEY, JSON.stringify({ runId: this.params.request_id, mode: this.mode, params: this.params, acknowledged: false, cancelRequested: this.cancelRequested })); }
      catch { this.update({ error: 'Reload recovery could not be saved. Keep this tab open.' }); }
      const response = await this.client.createScanRun(this.params);
      if (response.error || !response.data) {
        if (response.httpStatus && [400, 409, 422].includes(response.httpStatus)) {
          this.update({ status: 'failed', error: response.error ?? 'Start rejected.', autoScan: false });
          try { this.storage().removeItem(ACTIVE_KEY); } catch { /* next reload confirms missing job */ }
          return;
        }
        throw new Error(response.error || 'Scan start response lost.');
      }
      this.acknowledged = true;
      this.update({ runId: response.data.run_id, startedAt: response.data.created_at, status: 'queued' });
      try { this.storage().setItem(ACTIVE_KEY, JSON.stringify({ runId: response.data.run_id, mode: this.mode, params: this.params, acknowledged: true, cancelRequested: this.cancelRequested })); }
      catch { this.update({ error: 'Scan is active, but reload recovery could not be saved. Keep this tab open.' }); }
      this.creating = false;
      if (this.cancelRequested) await this.cancel();
      else void this.poll();
    } catch (error) {
      this.update({ status: 'disconnected', error: `Start unconfirmed; checking the same request. ${String(error)}`, autoScan: false });
      this.creating = false;
      if (this.cancelRequested) await this.cancel(); else void this.poll();
    } finally { this.creating = false; }
  };
  reconnect = () => { this.clearTimer(); void this.poll(); };
  cancel = async () => {
    this.setAutoScan(false); this.cancelRequested = true; this.clearTimer();
    const runId = this.state.runId;
    if (runId) {
      try { this.storage().setItem(ACTIVE_KEY, JSON.stringify({ runId, mode: this.mode, params: this.params, acknowledged: this.acknowledged, cancelRequested: true })); } catch { /* stop is still owned by this tab */ }
    }
    if (!runId || this.creating) return; // A pending POST is owned here and honours stop when it returns.
    this.cancelError = null;
    this.update({ status: 'cancelling', error: null });
    try {
      const response = await this.client.cancelScanRun(runId);
      if (this.state.runId !== runId || !scanIsBusy(this.state.status)) return;
      if (response.error) throw new Error(response.error);
      // Cancellation can race completion; only the job endpoint establishes the terminal state.
    } catch (error) {
      if (this.state.runId !== runId || !scanIsBusy(this.state.status)) return;
      this.cancelError = `Stop not confirmed: ${String(error)}. Retry stop.`;
      this.update({ status: 'disconnected', error: this.cancelError });
    }
    void this.poll();
  };
  private poll = async () => {
    const runId = this.state.runId;
    if (!runId || this.polling || !scanIsBusy(this.state.status)) return;
    this.polling = true;
    try {
      const response = await this.client.getScanRun(runId, { silent: true });
      if (response.httpStatus === 404) {
        if (!this.acknowledged && this.params) {
          // A delayed POST may arrive after this GET. Reuse its identity until
          // creation is acknowledged; absence alone must never authorize a new UUID.
          const created = await this.client.createScanRun({ ...this.params, request_id: runId });
          if (created.error || !created.data) throw new Error(created.error || 'Start still unconfirmed.');
          this.acknowledged = true;
          try { this.storage().setItem(ACTIVE_KEY, JSON.stringify({ runId, mode: this.mode, params: this.params, acknowledged: true, cancelRequested: this.cancelRequested })); } catch { /* identity remains in memory */ }
          this.update({ status: 'queued', startedAt: created.data.created_at, error: null });
          if (this.cancelRequested) { this.restoredCancellation = false; await this.cancel(); }
          this.schedule(() => void this.poll(), 2000);
          return;
        }
        this.update({ status: 'failed', autoScan: false, error: 'The server no longer retains this scan (restart or expiry). You can start a new scan.' });
        try { this.storage().removeItem(ACTIVE_KEY); } catch { /* no active job remains */ }
        return;
      }
      if (response.error || !response.data) throw new Error(response.error || 'No scan response.');
      const job = response.data;
      if (!this.acknowledged) {
        try { this.storage().setItem(ACTIVE_KEY, JSON.stringify({ runId, mode: this.mode, params: this.params, acknowledged: true, cancelRequested: this.cancelRequested })); }
        catch { /* current tab still owns the confirmed job */ }
      }
      this.acknowledged = true;
      const active = ['queued', 'running'].includes(job.status);
      this.update({ status: active && this.cancelRequested && !this.cancelError ? 'cancelling' : job.status, progress: job.progress, total: job.total, currentSymbol: job.current_symbol ?? null,
        signalsFound: job.signals?.length ?? 0, rejections: summarizeRejections(job.rejections),
        startedAt: job.started_at ?? job.created_at, completedAt: job.completed_at ?? null, error: job.error ?? (active ? this.cancelError : null) });
      if (active && this.restoredCancellation) { this.restoredCancellation = false; await this.cancel(); }
      if (job.status === 'completed') {
        const meta = job.metadata ?? {};
        try {
          this.history.saveScan({ id: runId, timestamp: job.completed_at ?? job.created_at,
            mode: meta.mode ?? this.mode?.name ?? 'unknown', profile: this.mode?.profile ?? 'unknown',
            timeframes: meta.applied_timeframes ?? this.mode?.timeframes ?? [],
            symbolsScanned: meta.scanned ?? job.total, signalsGenerated: job.signals?.length ?? 0,
            signalsRejected: job.rejections?.total_rejected ?? 0,
            effectiveMinScore: meta.effective_min_score ?? this.mode?.min_confluence_score ?? 0,
            rejectionBreakdown: job.rejections?.by_reason, rejectionSummary: job.rejections as any,
            results: (job.signals ?? []).map(signal => convertSignalToScanResult({ ...signal, timestamp: job.completed_at ?? job.created_at })) });
        } catch { this.update({ error: 'Results are available in this tab, but browser history could not be saved.', autoScan: false }); }
        this.update({ historyVersion: this.state.historyVersion + 1 });
      }
      if (['completed', 'failed', 'cancelled'].includes(job.status)) {
        try { this.storage().removeItem(ACTIVE_KEY); } catch { /* receipt id is idempotent on reload */ }
        if (job.status === 'completed' && this.state.autoScan && this.mode && !this.cancelRequested)
          this.schedule(() => { if (this.state.autoScan && this.mode) void this.start(this.mode, this.params); }, 5000);
        else this.update({ autoScan: false });
      } else this.schedule(() => void this.poll(), 2000);
    } catch (error) {
      this.update({ status: 'disconnected', error: `Scan connection lost; the server may still be working. ${String(error)}` });
      this.schedule(() => void this.poll(), 10000);
    } finally { this.polling = false; }
  };
}
export const scanRunService = new ScanRunService();

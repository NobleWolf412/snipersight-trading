import { api, type ReplayStepResponse } from '@/utils/api';

type Session = NonNullable<Awaited<ReturnType<typeof api.createReplaySession>>['data']>;
type LoadParams = Parameters<typeof api.createReplaySession>[0];
export type ReplayPlayState = 'idle' | 'loading' | 'ready' | 'playing' | 'paused' | 'ended';
interface Snapshot {
  playState: ReplayPlayState; session: Session | null; step: ReplayStepResponse | null;
  errorMsg: string | null; moveTarget: number | null; scoreHistory: Map<number, number>; signalIndices: Set<number>;
}
/** Serial cursor mutations plus generation fencing for reload, exit and late responses. */
export class ReplaySessionController {
  private state: Snapshot = { playState: 'idle', session: null, step: null, errorMsg: null, moveTarget: null,
    scoreHistory: new Map(), signalIndices: new Set() };
  private listeners = new Set<() => void>();
  private generation = 0;
  private navigation = 0;
  private queue: Promise<void> = Promise.resolve();
  private cleanupIds = new Set<string>();
  getSnapshot = () => this.state;
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  constructor(private client = api) {}
  private update(patch: Partial<Snapshot>) { this.state = { ...this.state, ...patch }; this.listeners.forEach(fn => fn()); }
  private async cleanup(id: string) {
    this.cleanupIds.add(id);
    const result = await this.client.deleteReplaySession(id);
    if (result.error) throw new Error(`Replay cleanup failed: ${result.error}`);
    this.cleanupIds.delete(id);
  }
  close = async () => {
    const generation = ++this.generation;
    const session = this.state.session;
    this.update({ playState: 'idle', session: null, step: null, errorMsg: null, moveTarget: null, scoreHistory: new Map(), signalIndices: new Set() });
    if (session) this.cleanupIds.add(session.session_id);
    await this.queue;
    try { for (const id of this.cleanupIds) await this.cleanup(id); }
    catch (error) { if (generation === this.generation) this.update({ errorMsg: String(error) }); }
  };
  load = async (params: LoadParams) => {
    const generation = ++this.generation;
    const prior = this.state.session;
    if (prior) this.cleanupIds.add(prior.session_id);
    this.update({ playState: 'loading', session: null, step: null, errorMsg: null, moveTarget: null, scoreHistory: new Map(), signalIndices: new Set() });
    try {
      await this.queue;
      for (const id of this.cleanupIds) await this.cleanup(id);
      if (generation !== this.generation) return;
      const response = await this.client.createReplaySession(params);
      if (response.error || !response.data) throw new Error(response.error || 'No replay session returned.');
      const session = response.data;
      if (generation !== this.generation) { await this.cleanup(session.session_id); return; }
      this.update({ session, playState: 'ready' });
      await this.stepBy(1);
    } catch (error) {
      if (generation === this.generation) this.update({ playState: this.state.session ? 'paused' : 'idle', errorMsg: String(error) });
    }
  };
  setPlayState = (playState: ReplayPlayState) => this.update({ playState });
  cancelMove = () => {
    ++this.navigation;
    this.update({ moveTarget: null, playState: 'paused' });
  };
  togglePlay = () => {
    if (this.state.moveTarget !== null) { this.cancelMove(); return; }
    if (this.state.playState === 'playing') this.update({ playState: 'paused' });
    else if (['ready', 'paused'].includes(this.state.playState)) this.update({ playState: 'playing' });
    else if (this.state.playState === 'ended') {
      const reset = this.seek(0);
      const generation = this.generation, navigation = this.navigation;
      void reset.then(() => {
        if (generation === this.generation && navigation === this.navigation &&
            this.state.step?.index === 0 && this.state.playState === 'paused' && !this.state.errorMsg) {
          this.update({ playState: 'playing' });
        }
      });
    }
  };
  private move(value: number, absolute: boolean, automatic: boolean) {
    const generation = this.generation;
    const session = this.state.session;
    if (!session || !Number.isFinite(value)) return Promise.resolve();
    const navigation = automatic ? this.navigation : ++this.navigation;
    const current = () => generation === this.generation && navigation === this.navigation;
    if (!automatic) this.update({ playState: 'paused' });
    this.queue = this.queue.then(async () => {
      if (!current() || (automatic && this.state.playState !== 'playing')) return;
      // Reconcile even after a committed step whose response was lost.
      const cursor = await this.client.getReplaySession(session.session_id);
      if (!current()) return;
      if (cursor.error || !cursor.data) throw new Error(cursor.error || 'Replay cursor unavailable.');
      let index = cursor.data.current_index;
      const target = Math.max(0, Math.min(session.total_bars - 1,
        Math.trunc(absolute ? value : index + value)));
      this.update({ moveTarget: target, errorMsg: null });
      // A multi-bar POST can exceed the request timeout. Publish one closed bar
      // per request. Backward seeks start at zero so the backend never rebuilds
      // a long causal prefix inside a single request after a cached rewind.
      let rewind = target < index;
      do {
        if (!current() || (automatic && this.state.playState !== 'playing')) return;
        const delta = rewind ? -index : index < target ? 1 : 0;
        const expected = Math.max(0, index + delta);
        const result = await this.client.stepReplay(session.session_id, delta);
        if (!current()) return;
        if (result.error || !result.data) throw new Error(result.error || 'Replay frame missing.');
        const step = result.data;
        if (step.index !== expected) throw new Error('Replay cursor changed unexpectedly. Retry to reconcile.');
        index = step.index;
        rewind = false;
        const scoreHistory = new Map(this.state.scoreHistory);
        const signalIndices = new Set(this.state.signalIndices);
        if (step.confluence?.total_score != null) scoreHistory.set(step.index, step.confluence.total_score);
        if (step.signal_fired) signalIndices.add(step.index);
        this.update({ step, scoreHistory, signalIndices, errorMsg: null,
          playState: index >= session.total_bars - 1 ? 'ended' : automatic ? this.state.playState : 'paused' });
      } while (index < target);
    }).catch(error => {
      if (current()) this.update({ errorMsg: String(error), playState: 'paused' });
    }).finally(() => {
      if (current()) this.update({ moveTarget: null });
    });
    return this.queue;
  }
  stepBy = (n: number, automatic = false) => this.move(n, false, automatic);
  seek = (index: number) => this.move(index, true, false);
  reset = () => this.seek(0);
}

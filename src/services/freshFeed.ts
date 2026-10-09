type Response<T> = { data?: T; error?: string };
export class FreshFeed<T> {
  private state: { data: T | null; error?: string; loading: boolean; receivedAt?: string } = { data: null, loading: true };
  private generation = 0;
  private expiry?: ReturnType<typeof setTimeout>;
  private listeners = new Set<() => void>();
  constructor(private fetch: () => Promise<Response<T>>, private deadline: (value: T, now: number) => number) {}
  getSnapshot = () => this.state;
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  private update(patch: Partial<typeof this.state>) { this.state = { ...this.state, ...patch }; this.listeners.forEach(fn => fn()); }
  stop = () => { this.generation++; clearTimeout(this.expiry); this.update({ data: null, loading: false }); };
  refresh = async () => {
    const generation = ++this.generation;
    clearTimeout(this.expiry);
    this.update({ data: null, error: undefined, loading: true });
    try {
      const response = await this.fetch();
      if (generation !== this.generation) return;
      if (response.error || !response.data) throw new Error(response.error || 'Feed unavailable.');
      const now = Date.now();
      const expires = this.deadline(response.data, now);
      if (!Number.isFinite(expires) || expires <= now) throw new Error('Required market evidence is missing or expired.');
      this.update({ data: response.data, receivedAt: new Date(now).toISOString(), loading: false });
      this.expiry = setTimeout(() => this.update({ data: null, error: 'Feed expired. Refresh to reconnect.' }), expires - now);
    } catch (error) {
      if (generation === this.generation) this.update({ data: null, error: String(error), loading: false });
    }
  };
}

export function observationDeadline(observed: string | undefined, maxAge: number, now: number) {
  const timestamp = Date.parse(observed ?? '');
  return Number.isFinite(timestamp) && timestamp <= now ? timestamp + maxAge : NaN;
}

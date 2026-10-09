import { useEffect, useState, useSyncExternalStore } from 'react';
import { FreshFeed } from '@/services/freshFeed';

/** Loader and policy are fixed for this mounted feed; each feed expires independently. */
export function useFreshFeed<T>(loader: () => Promise<{ data?: T; error?: string }>, deadline: (data: T, now: number) => number) {
  const [owner] = useState(() => new FreshFeed(loader, deadline));
  const snapshot = useSyncExternalStore(owner.subscribe, owner.getSnapshot, owner.getSnapshot);
  useEffect(() => {
    void owner.refresh();
    const timer = setInterval(() => { if (!owner.getSnapshot().loading) void owner.refresh(); }, 60000);
    return () => { clearInterval(timer); owner.stop(); };
  }, [owner]);
  return { ...snapshot, retry: owner.refresh };
}

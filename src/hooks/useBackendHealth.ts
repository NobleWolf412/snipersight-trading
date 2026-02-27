import { useEffect, useState } from 'react';
import { api } from '@/utils/api';

export function useBackendHealth(pollMs = 3000) {
  const [online, setOnline] = useState<boolean>(false);
  const [lastChecked, setLastChecked] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let timer: ReturnType<typeof setInterval> | null = null;

    const check = async () => {
      try {
        const res = await api.healthCheck();
        if (!mounted) return;
        setLastChecked(Date.now());
        if (res.data && (res as any).data.status === 'healthy') {
          setOnline(true);
          setError(null);
        } else if (res.error) {
          setOnline(false);
          setError(res.error);
        } else {
          setOnline(false);
        }
      } catch (e: any) {
        if (!mounted) return;
        setOnline(false);
        setError(e?.message || 'health check failed');
        setLastChecked(Date.now());
      }
    };

    // initial check and polling
    check();
    timer = setInterval(check, pollMs);

    return () => {
      mounted = false;
      if (timer) clearInterval(timer);
    };
  }, [pollMs]);

  return { online, lastChecked, error };
}

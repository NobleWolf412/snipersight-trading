import { useEffect, useState } from 'react';
import { api, type ScannerRecommendation } from '@/utils/api';

export const unavailableRecommendation = (reason: string): ScannerRecommendation => ({
  status: 'unavailable', mode: null, reason, confidence: 'unavailable', warning: null,
});

export function recommendationIsFresh(value: ScannerRecommendation, now = Date.now()) {
  const observed = Date.parse(value.timestamp ?? '');
  const expires = Date.parse(value.expires_at ?? '');
  return Number.isFinite(observed) && Number.isFinite(expires) && observed <= now && now < expires;
}

export function useScannerRecommendation() {
  const [recommendation, setRecommendation] = useState<ScannerRecommendation>(
    () => unavailableRecommendation('Loading market analysis…'),
  );
  useEffect(() => {
    let stopped = false;
    let pending = false;
    let expiry: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      if (pending || stopped) return;
      pending = true;
      try {
        const response = await api.getScannerRecommendation();
        if (stopped) return;
        clearTimeout(expiry);
        const value = response.data;
        if (!value || !['available', 'stand_aside', 'unavailable'].includes(value.status)) {
          setRecommendation(unavailableRecommendation('Market analysis is unavailable. You can still choose a fixed mode.'));
        } else if (value.status === 'unavailable' || !recommendationIsFresh(value)) {
          setRecommendation(unavailableRecommendation(value.status === 'unavailable' ? value.reason : 'Market analysis has expired.'));
        } else {
          setRecommendation(value);
          expiry = setTimeout(() => setRecommendation(unavailableRecommendation('Market analysis has expired.')),
            Math.max(0, Date.parse(value.expires_at!) - Date.now()));
        }
      } catch {
        if (!stopped) setRecommendation(unavailableRecommendation('Market analysis is unavailable.'));
      } finally {
        pending = false;
      }
    };
    void refresh();
    const interval = setInterval(() => { void refresh(); }, 60_000);
    const onVisible = () => { if (document.visibilityState === 'visible') void refresh(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => { stopped = true; clearInterval(interval); clearTimeout(expiry); document.removeEventListener('visibilitychange', onVisible); };
  }, []);
  return recommendation;
}

import { useEffect, useState } from 'react';
import type { SystemStatusData, Metric } from '@/types/landing';
import { initialMetrics } from '@/config/landingConfig';
import { version } from '@/version';

export function useTelemetry() {
  const [metrics, setMetrics] = useState<Metric[]>(initialMetrics);
  const [system, setSystem] = useState<SystemStatusData>({
    exchangeStatus: 'connected',
    latencyMs: 0,
    activeTargets: 0,
    signalsRejected: 0,
    version
  });

  useEffect(() => {
    let mounted = true;
    let latencyBaseline = performance.now();

    const interval = setInterval(() => {
      if (!mounted) return;
      const now = performance.now();
      const simulatedLatency = Math.round(Math.random() * 40 + 10); // 10-50ms
      const activeTargets = Math.round(Math.random() * 5);
      const rejected = Math.round(activeTargets * 0.6);

      setSystem(s => ({
        ...s,
        latencyMs: simulatedLatency,
        activeTargets,
        signalsRejected: rejected
      }));

      setMetrics(m => m.map(metric => {
        switch (metric.key) {
          case 'activeTargets':
            return { ...metric, value: activeTargets };
          case 'signalsRejected':
            return { ...metric, value: rejected };
          case 'latencyMs':
            return { ...metric, value: simulatedLatency };
          case 'exchangeStatus':
            return { ...metric, value: 'Connected' };
          default:
            return metric;
        }
      }));

      latencyBaseline = now;
    }, 4000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { metrics, system };
}

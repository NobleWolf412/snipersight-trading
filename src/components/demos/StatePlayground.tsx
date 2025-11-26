import { useAtom } from 'jotai';
import { selectedSymbolAtom, timeframeAtom, confidenceFilterAtom } from '@/state/atoms';
import { useUIStore } from '@/state/uiStore';
import { AnimatedCard } from './AnimatedCard';

export function StatePlayground() {
  const [symbol, setSymbol] = useAtom(selectedSymbolAtom);
  const [tf, setTf] = useAtom(timeframeAtom);
  const [minConfidence, setMinConfidence] = useAtom(confidenceFilterAtom);
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <AnimatedCard title="Zustand UI Store" description="Quick toggles for layout & theme.">
        <div className="flex items-center gap-3">
          <button className="btn" onClick={toggleSidebar}>
            Toggle Sidebar ({sidebarOpen ? 'Open' : 'Closed'})
          </button>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as any)}
            className="rounded border bg-bg p-2"
          >
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
      </AnimatedCard>

      <AnimatedCard title="Jotai Trading State" description="Symbol, timeframe and confidence filter.">
        <div className="flex flex-col gap-3">
          <input
            className="rounded border bg-bg p-2"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="Symbol e.g. BTC/USDT"
          />
          <select
            value={tf}
            onChange={(e) => setTf(e.target.value as any)}
            className="rounded border bg-bg p-2"
          >
            {['1W','1D','4H','1H','15m','5m'].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <label className="text-sm">Min Confidence: {minConfidence}</label>
          <input
            type="range"
            min={0}
            max={100}
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
          />
        </div>
      </AnimatedCard>
    </div>
  );
}

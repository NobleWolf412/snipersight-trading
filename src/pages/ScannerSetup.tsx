import { TopBar } from '@/components/TopBar/TopBar';
import { Link } from 'react-router-dom';

export function ScannerSetup() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/95 backdrop-blur-sm">
        <TopBar />
      </header>
      <main className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        <div className="space-y-3">
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight">Scanner Configuration</h1>
          <p className="text-muted-foreground max-w-2xl">Adjust reconnaissance scanner parameters, market universes, confluence weighting, and operational cadence.</p>
        </div>

        <div className="border border-border/50 rounded-xl p-6 bg-card/50 backdrop-blur-sm space-y-6">
          <h2 className="text-xl font-semibold">Coming Soon</h2>
          <p className="text-sm text-muted-foreground">UI controls for pattern filters, timeframe sets, confluence factor weights, risk gates, and scan scheduling will appear here.</p>
          <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
            <li>Timeframe set editor (e.g. M5 / M15 / H1 / H4)</li>
            <li>Pattern filter toggles (OB, FVG, Liquidity sweep, BOS, CHoCH)</li>
            <li>Confluence factor weighting sliders (HTF alignment, volume profile, volatility regime, correlation)</li>
            <li>Risk gates (max setups per session, min quality score)</li>
            <li>Notification preferences & escalation paths</li>
          </ul>
        </div>

        <div className="flex items-center gap-4">
          <Link to="/" className="px-5 py-2 rounded-md border border-border/60 hover:border-accent/50 transition-colors text-sm">← Back to Landing</Link>
          <button disabled className="px-5 py-2 rounded-md bg-accent/20 text-accent border border-accent/30 text-sm cursor-not-allowed">Save Configuration (inactive)</button>
        </div>
      </main>
    </div>
  );
}

export default ScannerSetup;

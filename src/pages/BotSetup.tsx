import { TopBar } from '@/components/TopBar/TopBar';
import { Link } from 'react-router-dom';

export function BotSetup() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/95 backdrop-blur-sm">
        <TopBar />
      </header>
      <main className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        <div className="space-y-3">
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight">Autonomous Bot Configuration</h1>
          <p className="text-muted-foreground max-w-2xl">Control execution parameters, risk constraints, position management rules, and environment/credentials.</p>
        </div>

        <div className="border border-border/50 rounded-xl p-6 bg-card/50 backdrop-blur-sm space-y-6">
          <h2 className="text-xl font-semibold">Coming Soon</h2>
          <p className="text-sm text-muted-foreground">Panels for API key management, strategy enablement, risk ceilings, correlation thresholds, and telemetry toggles will be added.</p>
          <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
            <li>Exchange & wallet authentication status</li>
            <li>Global risk limits (max portfolio exposure, per-asset cap)</li>
            <li>Correlation matrix thresholds & decay settings</li>
            <li>Position management rules (breakeven delay, trailing activation)</li>
            <li>Execution preferences (limit vs market bias, slippage guard)</li>
            <li>Telemetry sampling / verbosity controls</li>
          </ul>
        </div>

        <div className="flex items-center gap-4">
          <Link to="/" className="px-5 py-2 rounded-md border border-border/60 hover:border-primary/50 transition-colors text-sm">← Back to Landing</Link>
          <button disabled className="px-5 py-2 rounded-md bg-primary/20 text-primary border border-primary/30 text-sm cursor-not-allowed">Deploy Bot (inactive)</button>
        </div>
      </main>
    </div>
  );
}

export default BotSetup;

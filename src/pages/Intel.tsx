
import { PageContainer } from '@/components/layout/PageContainer';
import { HomeButton } from '@/components/layout/HomeButton';
import { FourYearCycleGauge } from '@/components/market/FourYearCycleGauge';
import { BTCCycleIntel } from '@/components/market/BTCCycleIntel';
import { useSymbolCycles } from '@/hooks/useSymbolCycles';
import { useMarketRegime } from '@/hooks/useMarketRegime';

// New Educational Components
import { NewsTicker } from '@/components/intel/NewsTicker';
import { MarketEditorial } from '@/components/intel/MarketEditorial';
import { CycleTheoryExplainer } from '@/components/intel/CycleTheoryExplainer';
import { DominanceRadar } from '@/components/intel/DominanceRadar';
import { NarrativeTracker } from '@/components/intel/NarrativeTracker';

export function Intel() {
  const regimeProps = useMarketRegime('scanner');

  // Correct hook usage: Object options
  const { cycles, btcContext } = useSymbolCycles({
    symbols: ['BTCUSDT'],
    exchange: 'phemex'
  });

  // Construct data for the gauge from the context, or use fallback
  const gaugeData = btcContext?.four_year_cycle || {
    days_since_low: 0,
    days_until_expected_low: 0,
    cycle_position_pct: 0,
    phase: 'UNKNOWN',
    phase_progress_pct: 0,
    last_low: { date: '2022-11-21', price: 15476, event: 'FTX Collapse' },
    expected_next_low: '2026-10-15',
    macro_bias: 'NEUTRAL',
    confidence: 0,
    zones: { is_danger_zone: false, is_opportunity_zone: false }
  };

  return (
    <PageContainer id="main-content" wide>
      <div className="flex flex-col min-h-screen bg-background">

        {/* 1. NEWS TICKER (Fixed at top capability usually, but inline here) */}
        <NewsTicker />

        <div className="max-w-[1400px] w-full mx-auto px-4 md:px-8 py-8 space-y-12">

          {/* Navigation */}
          <div className="flex items-center gap-4 text-muted-foreground hover:text-foreground transition-colors">
            <HomeButton />
            <span className="text-sm font-mono uppercase tracking-widest hud-text-green">Global Intelligence Command</span>
          </div>

          {/* 2. EXECUTIVE SUMMARY (Editorial) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Editorial Card */}
            <div className="lg:col-span-7 glass-card glow-border-green p-6 lg:p-8 rounded-2xl relative overflow-hidden group transition-all duration-500 hover:shadow-[0_0_40px_rgba(0,255,170,0.1)]">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-40 pointer-events-none group-hover:opacity-60 transition-opacity duration-700" />
              <div className="relative z-10">
                <MarketEditorial
                  regime={regimeProps}
                  btcContext={btcContext}
                />
              </div>
            </div>

            {/* Sidebar: Dominance + Narrative */}
            <div className="lg:col-span-5 flex flex-col gap-6">
              {/* Capital Flow Radar */}
              <div className="glass-card glow-border-blue p-6 rounded-2xl relative overflow-hidden group transition-all duration-500 hover:shadow-[0_0_40px_rgba(59,130,246,0.1)]">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-blue-500/5 via-transparent to-transparent opacity-40 pointer-events-none group-hover:opacity-60 transition-opacity duration-700" />
                <div className="relative z-10">
                  <h3 className="text-sm font-bold text-blue-400 uppercase mb-4 tracking-widest flex items-center gap-2">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                    Capital Flow Radar
                  </h3>
                  <DominanceRadar />
                </div>
              </div>
              <NarrativeTracker />
            </div>
          </div>

          {/* Glowing Divider */}
          <div className="w-full h-px bg-gradient-to-r from-transparent via-green-500/30 to-transparent" />

          {/* 3. CYCLE THEORY EDUCATION SECTION */}
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
            <div className="flex flex-col md:flex-row items-end justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold font-mono uppercase tracking-tight hud-headline hud-text-green">Cycle Intelligence</h2>
                <p className="text-muted-foreground mt-2 max-w-2xl">
                  Price action moves in waves. We track the 4-Year Macro Cycle and fractal daily/weekly cycles to determine structural health.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
              {/* Theory: How it works */}
              <div className="glass-card glow-border-amber p-6 rounded-2xl relative overflow-hidden group transition-all duration-500 hover:shadow-[0_0_40px_rgba(251,191,36,0.1)]">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_var(--tw-gradient-stops))] from-amber-500/5 via-transparent to-transparent opacity-40 pointer-events-none group-hover:opacity-60 transition-opacity duration-700" />
                <div className="relative z-10">
                  <CycleTheoryExplainer className="h-full" />
                </div>
              </div>

              {/* Data: Where we are */}
              <div className="relative group">
                {/* Glow effect behind the gauge */}
                <div className="absolute -inset-1 bg-gradient-to-r from-green-500/20 via-emerald-500/10 to-green-500/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
                <div className="relative">
                  <FourYearCycleGauge
                    data={gaugeData}
                    className="glow-border-green"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Glowing Divider */}
          <div className="w-full h-px bg-gradient-to-r from-transparent via-green-500/30 to-transparent" />

          {/* 4. DEEP DIVE (The "Data" Section) */}
          <div className="space-y-6 pb-20 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-300">
            <h3 className="text-lg font-bold text-green-400 uppercase tracking-widest hud-headline">
              Deep Dive Analysis
            </h3>
            {/* Using the full-featured BTC Cycle Intel component here */}
            <div className="glass-card glow-border-green p-6 rounded-2xl">
              <BTCCycleIntel autoRefresh={false} />
            </div>
          </div>

        </div>
      </div>
    </PageContainer>
  );
}

export default Intel;


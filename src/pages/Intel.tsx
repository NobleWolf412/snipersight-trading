
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
    <PageContainer id="main-content" fullWidth>
      <div className="flex flex-col min-h-screen bg-background">

        {/* 1. NEWS TICKER (Fixed at top capability usually, but inline here) */}
        <NewsTicker />

        <div className="max-w-[1400px] w-full mx-auto px-4 md:px-8 py-8 space-y-12">

          {/* Navigation */}
          <div className="flex items-center gap-4 text-muted-foreground hover:text-foreground transition-colors">
            <HomeButton />
            <span className="text-sm font-mono uppercase tracking-widest">Global Intelligence Command</span>
          </div>

          {/* 2. EXECUTIVE SUMMARY (Editorial) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="lg:col-span-7">
              <MarketEditorial
                regime={regimeProps}
                btcContext={btcContext}
              />
            </div>
            {/* Dominance Radar as a "Side Bar" Context */}
            <div className="lg:col-span-5 flex flex-col gap-6">
              <div className="bg-card/20 p-6 rounded-2xl border border-border/40">
                <h3 className="text-sm font-bold text-muted-foreground uppercase mb-4 tracking-widest">
                  Capital Flow Radar
                </h3>
                <DominanceRadar />
              </div>
              <NarrativeTracker />
            </div>
          </div>

          {/* Divider */}
          <div className="w-full h-px bg-border/30" />

          {/* 3. CYCLE THEORY EDUCATION SECTION */}
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
            <div className="flex flex-col md:flex-row items-end justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold font-mono uppercase tracking-tight">Cycle Intelligence</h2>
                <p className="text-muted-foreground mt-2 max-w-2xl">
                  Price action moves in waves. We track the 4-Year Macro Cycle and fractal daily/weekly cycles to determine structural health.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
              {/* Theory: How it works */}
              <CycleTheoryExplainer className="h-full" />

              {/* Data: Where we are */}
              <div className="bg-card/20 rounded-2xl border border-border/40 p-6 flex flex-col items-center justify-center relative overflow-hidden">
                <div className="absolute top-4 left-6 z-10">
                  <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest">
                    Live Macro Position
                  </span>
                </div>
                <FourYearCycleGauge
                  data={gaugeData}
                  className="scale-90 md:scale-100 border-none bg-transparent"
                />
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="w-full h-px bg-border/30" />

          {/* 4. DEEP DIVE (The "Data" Section) */}
          <div className="space-y-6 pb-20 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-300">
            <h3 className="text-lg font-bold text-muted-foreground uppercase tracking-widest">
              Deep Dive Analysis
            </h3>
            {/* Using the full-featured BTC Cycle Intel component here */}
            <BTCCycleIntel autoRefresh={false} />
          </div>

        </div>
      </div>
    </PageContainer>
  );
}

export default Intel;

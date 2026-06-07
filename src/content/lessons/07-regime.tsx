import { FlipCard } from '@/components/lessons/primitives';
import { RegimeQuadrant } from '@/components/hud';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

// Demonstration values — drives the hero RegimeQuadrant for the chapter.
// Operator-visible coords; not tuned thresholds.
// SYNC: backend/analysis/regime_detector.py
const DEMO_BTC_ADX = 32;
const DEMO_BTC_ATR_PCT = 1.8;
const DEMO_ALT_ADX = 18;
const DEMO_ALT_ATR_PCT = 3.4;

export default function RegimeBody() {
  return (
    <>
      <ChapterPara>
        Markets cycle between <strong>trending, ranging, and chop</strong> regimes, and between{' '}
        <strong>volatility expansion and contraction</strong>. Regime detection is the discipline of
        classifying <em>which one you're in right now</em> before applying any strategy — trend-following
        bleeds in chop, mean-reversion blows up in trends. Volatility is{' '}
        <em>clustered</em> (Mandelbrot), not i.i.d., which is the only reason regimes exist as a tradable
        concept.
      </ChapterPara>

      <HeroWrap caption="BTC currently in quiet trend; alt drifting toward chop">
        <RegimeQuadrant
          symbol="BTC"
          trendStrength={DEMO_BTC_ADX}
          volatility={DEMO_BTC_ATR_PCT}
          comparison={{
            symbol: 'ALT',
            trendStrength: DEMO_ALT_ADX,
            volatility: DEMO_ALT_ATR_PCT,
          }}
        />
      </HeroWrap>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          The toolkit: <strong>percentage ATR</strong> (normalized volatility — never absolute),{' '}
          <strong>ADX</strong> (trend magnitude, direction-agnostic), <strong>Choppiness Index</strong>{' '}
          (Dreiss — range vs trend), <strong>Hurst exponent</strong> (persistence). At the academic tier,
          Hamilton's regime-switching Markov models capture <em>transition probabilities</em> between latent
          regimes — heuristics don't.
        </ChapterPara>
        <ChapterPara>
          Percentage ATR matters because absolute ATR is price-dependent. An ATR of $200 on BTC at $100k is
          calm; the same $200 on a $5k alt is a meltdown. The bot uses ATR% to make regimes comparable across
          symbols — and CLAUDE.md flags absolute ATR as a regression to never reintroduce.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT MATTERS">
        <ChapterPara>
          Volatility clusters. Mandelbrot's empirical finding — confirmed across every liquid market — is
          that large price changes are followed by more large price changes, small by small. If volatility
          were i.i.d., there would be no regimes to detect. Because it isn't, you can measure the current
          cluster and gate your strategy on it.
        </ChapterPara>
        <ChapterPara>
          Crypto-specific baselines: BTC/ETH 4h ATR% sits 0.8-2% in normal times; large caps 1.5-3%; mid
          caps 2-5%; small caps 3-10%, spiking past 20% in flushes. Calibrate detectors against these
          benchmarks.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="regime.adx-direction"
            front={<>"ADX tells me direction."</>}
            back={
              <>
                It doesn't. ADX is magnitude only. +DI and −DI carry direction. ADX &gt; 25 = strong trend;
                price action still has to tell you which way.
              </>
            }
          />
          <FlipCard
            localStorageKey="regime.absolute-atr"
            front={<>"BTC's $200 ATR &gt; SOL's $20 ATR."</>}
            back={
              <>
                Meaningless. Percentage ATR is the correct comparison. Standing fix — never reintroduce
                absolute ATR.
              </>
            }
          />
          <FlipCard
            localStorageKey="regime.chop-direction"
            front={<>"Choppiness Index tells me direction."</>}
            back={
              <>
                It doesn't — only range-vs-trend. Below ~38.2 = trending efficiently; above ~61.8 = ranging.
                The 38.2-61.8 band is transitional and the source of most false signals.
              </>
            }
          />
          <FlipCard
            localStorageKey="regime.vol-expansion"
            front={<>"Volatility expansion = trend."</>}
            back={
              <>
                Expansion = range widened. It can be a trending breakout <em>or</em> a volatile chop. Trend
                strength (ADX / Hurst) must agree before calling it.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>Timeframe-dependent</strong> — a symbol can be trending on 1d and chopping on 15m. Bot's
            mode-aware critical-TF system exists for this.
          </li>
          <li>
            <strong>Hurst sample-hungry</strong> — most retail implementations are noisy under ~200 bars.
            Single-symbol Hurst deserves skepticism.
          </li>
          <li>
            <strong>Markov regime-switching</strong> — Hamilton 1989 is the foundational paper. Recent
            Bitcoin work (HMM, MS-GARCH) consistently identifies 2-4 latent regimes including a calm state.
          </li>
          <li>
            <strong>News breaks single bars, not regimes</strong> — single-bar spikes drop CHOP below 38.2
            briefly but the regime hasn't actually shifted. Pair with multi-bar confirmation.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

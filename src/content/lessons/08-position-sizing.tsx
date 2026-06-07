import { FlipCard } from '@/components/lessons/primitives';
import { KellyCurve } from '@/components/hud';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

// Demonstration values for the hero KellyCurve. f* = (1.5*0.55 - 0.45) / 1.5 ≈ 0.25.
// At 2f* (50% per bet), the log-growth rate hits zero. Past that — guaranteed
// ruin. The chart is the chapter's whole pitch.
const DEMO_WIN_RATE = 0.55;
const DEMO_PAYOFF = 1.5;
const DEMO_CURRENT_F = 0.12; // operator's "half Kelly" — under the cliff

export default function SizingBody() {
  return (
    <>
      <ChapterPara>
        Position sizing is the lever that converts a positive edge into long-run wealth — or destroys it.
        The subtle move operators miss is that this isn't a return-maximization problem in arithmetic mean —
        it's a <strong>log-growth maximization problem under non-ergodic compounding</strong>. Over-sizing
        past Kelly guarantees ruin <em>even with a real edge</em>.
      </ChapterPara>

      <HeroWrap caption="the single most important chart in this library">
        <KellyCurve
          winRate={DEMO_WIN_RATE}
          payoffRatio={DEMO_PAYOFF}
          bettingFraction={DEMO_CURRENT_F}
          label="// KELLY CURVE · 55% WIN @ 1.5R"
        />
      </HeroWrap>

      <ChapterSection title="// CORE MATH">
        <ChapterPara>
          Kelly criterion for a binary bet: <code>f* = (b·p − q) / b</code> where <code>b</code> is net odds
          (avgWin / avgLoss), <code>p</code> is win probability, <code>q</code> is 1 − p. Derived by
          maximizing <code>E[log W]</code>, the expected log-wealth.
        </ChapterPara>
        <ChapterPara>
          Expectancy in R units (after Van Tharp): <code>E = (W × avgWinR) − (L × avgLossR)</code>. A
          positive E in R-units is a necessary condition for sizing to even make sense.
        </ChapterPara>
        <ChapterPara>
          Volatility drag: <code>g ≈ μ − σ²/2</code>. The geometric (compounded) growth rate is the
          arithmetic mean minus half the variance. Leverage scales σ super-linearly — which is why a 3×
          leveraged ETF on flat-but-volatile chop decays.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// THE DEEP RESULT — ERGODICITY">
        <ChapterPara>
          A non-ergodic process has time-average return ≠ ensemble-average return. Trading a single account
          is non-ergodic — you cannot run 1000 parallel lives and average them. Peters and Taleb formalize
          this: optimizing for expected (arithmetic) value is a <em>category error</em> for a single agent
          compounding through time. You must optimize for the time-average growth rate, which is{' '}
          <code>E[log W]</code>, which is Kelly.
        </ChapterPara>
        <ChapterPara>
          Past <code>f*</code>, the inverted-U log-growth curve crosses zero and goes <em>negative</em>.{' '}
          <strong>At <code>2·f*</code> exactly, long-run growth = 0; past that, negative.</strong> This is
          the cliff most blown accounts die on.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="sizing.high-winrate"
            front={<>"High win rate means I can bet bigger."</>}
            back={
              <>
                False. A 90% / 0.1:1 system has the same Kelly as a 10% / 9:1 system. Sizing is governed by{' '}
                <em>expectancy and variance</em>, not win rate alone.
              </>
            }
          />
          <FlipCard
            localStorageKey="sizing.full-kelly"
            front={<>"Full Kelly is optimal."</>}
            back={
              <>
                Theoretically yes; practically catastrophic. Full Kelly assumes you know your edge precisely
                — you don't. Thorp's actual practice is fractional (half) Kelly.
              </>
            }
          />
          <FlipCard
            localStorageKey="sizing.leverage-free"
            front={<>"Leverage is free if my edge is real."</>}
            back={
              <>
                Volatility drag scales with leverage². 5× leverage in 3% daily-vol crypto bleeds ~1.1% / day
                to drag <em>before</em> the edge fights back.
              </>
            }
          />
          <FlipCard
            localStorageKey="sizing.average-return"
            front={<>"My average return justifies the size."</>}
            back={
              <>
                Average (arithmetic) return is meaningless to a single-account compounding trader. The
                relevant quantity is <em>time-average geometric</em> return. The ergodicity argument.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>ATR-based sizing</strong> — fixed % stop across symbols means very different
            probabilities. <code>stopDistance = k · ATR</code>; <code>positionSize = riskDollars /
            stopDistance</code>. Makes 1R mean the same across assets and regimes.
          </li>
          <li>
            <strong>Edge uncertainty → bet smaller</strong> — clean theorem: effective Kelly discounts by{' '}
            <code>(1 − σ_edge² / edge²)</code>. High uncertainty drives fractional Kelly toward zero.
          </li>
          <li>
            <strong>Risk per trade vs per day vs max drawdown</strong> — three different horizons of the same
            concept. All three caps need to fire.
          </li>
          <li>
            <strong>Kelly bound on leverage</strong> — Peters: optimal leverage = μ / σ². Past that, you're
            in the over-Kelly zone — guaranteed long-run loss even with positive drift.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

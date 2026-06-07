import { FlipCard } from '@/components/lessons/primitives';
import { SweepVsBreakoutTwin } from '@/components/lessons/widgets';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

export default function LiquiditySweepsBody() {
  return (
    <>
      <ChapterPara>
        A liquidity sweep is a brief excursion past a swing high or low that <strong>triggers resting stop
        orders, then closes back on the original side</strong>. Stops are explicit liquidity — every cluster
        of equal highs has stop-buys parked above. When an institution needs to enter a short with size, the
        cheapest way to find counterparties is to push price above the cluster, fill into the now-market buys,
        then reverse. Confusing a sweep with a breakout is the most expensive mistake in SMC.
      </ChapterPara>

      <HeroWrap caption="bullish swing-high shown — bar 6 sweep vs breakout · bearish is the mirror (swing-low side)">
        <SweepVsBreakoutTwin />
      </HeroWrap>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          Four hallmarks: (1) a real wick beyond the level, (2) a body close back inside, (3) a measurable
          reversal within a small bar window, (4) often a volume spike. The bot enforces a four-filter gate:
          range-position (only top/bottom 35% of the 50-bar range), level-age (
          <code>≥ 10 bars</code>), wick size (<code>≥ 0.15·ATR</code>), and mode-specific reversal window
          (3 bars SURGICAL → 12 OVERWATCH).
        </ChapterPara>
        <ChapterPara>
          Confirmation level (0-3) tiers off volume × reversal pattern. Climactic volume (3×+) earns level 3.
          The bot also detects <strong>double sweeps</strong> — same level swept twice — and{' '}
          <strong>sweep + structure-break combos</strong> via <code>validate_sweep_with_structure</code>.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT WORKS">
        <ChapterPara>
          The reversal is mechanical: the forced buying that drove the sweep is exhausted, the now-trapped
          breakout longs are about to puke, and the resting offer above supplies the down-move. This is
          Wyckoff's <strong>Spring</strong> (sweep below accumulation low → reverse up) and{' '}
          <strong>Upthrust</strong> (sweep above distribution high → reverse down), 100 years old,
          microstructure-grounded.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="sweep.vs-breakout"
            front={<>"Wick past = sweep."</>}
            back={
              <>
                Same first move, opposite implication. Body close <em>back inside</em> = sweep. Body close{' '}
                <em>beyond</em> = breakout/acceptance.
              </>
            }
          />
          <FlipCard
            localStorageKey="sweep.fresh-level"
            front={<>"Just-formed high counts."</>}
            back={
              <>
                A high that formed 3 bars ago has almost no parked stops. Bot enforces{' '}
                <code>min_level_age_bars = 10</code>.
              </>
            }
          />
          <FlipCard
            localStorageKey="sweep.body-poke"
            front={<>"Body-poke is a sweep."</>}
            back={
              <>
                Without a real wick (<code>≥ 0.15·ATR</code>), no stop-cluster was meaningfully tested. Bot
                rejects body-pokes.
              </>
            }
          />
          <FlipCard
            localStorageKey="sweep.lrlr"
            front={<>"Every sweep reverses."</>}
            back={
              <>
                <strong>LRLR (Low-Resistance Liquidity Run)</strong> doesn't reverse — it continues. ICT's
                HRLR vs LRLR distinction is the #1 live-trade mistake. Failed sweeps are continuation tells.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>HRLR vs LRLR</strong> — a level deeply respected (HRLR) reverses on sweep; a
            failure-swing-style level (LRLR) runs through with no friction. Telling them apart pre-trade is
            the discipline.
          </li>
          <li>
            <strong>Double sweeps</strong> — two consecutive sweeps at the same level often signal
            exhaustion: "they tried twice and failed".
          </li>
          <li>
            <strong>Sweep + BOS combo</strong> — a sweep followed within 10 bars by a BOS/CHoCH in the
            opposite direction is the highest-probability setup in the SMC stack.
          </li>
          <li>
            <strong>Asian-range setup</strong> — bullish daily bias often opens with London sweeping the
            Asian-range low (Judas swing) to fuel the rally.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

import { FlipCard } from '@/components/lessons/primitives';
import { FvgBuilder } from '@/components/lessons/widgets';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

export default function FvgBody() {
  return (
    <>
      <ChapterPara>
        A Fair Value Gap is a <strong>three-candle imbalance</strong>: candle 1's wick and candle 3's wick fail
        to overlap, leaving an unfilled band created by candle 2's displacement. The gap is the chart-visible
        footprint of one-sided delivery — buy and sell orders did not meet in the middle. Price tends to return
        and fill, but a <em>failed</em> fill (unfilled FVG) is the highest-momentum continuation tell.
      </ChapterPara>

      <HeroWrap caption="bullish FVG construction — press ▶ to step through; bearish is the mirror (flip the gap)">
        <FvgBuilder autoPlay />
      </HeroWrap>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          <strong>Bullish FVG</strong>: <code>candle[0].high &lt; candle[2].low</code>. <strong>Bearish</strong>:{' '}
          <code>candle[0].low &gt; candle[2].high</code>. The bot adds two gates: middle-candle overlap with the
          gap must be <code>≤ 10%</code>, and the gap size in ATR units must clear a mode-specific minimum (0.06
          SURGICAL → 0.45 OVERWATCH).
        </ChapterPara>
        <ChapterPara>
          Grading is multi-tier: A if <code>gap_atr ≥ 2.5×</code> the mode minimum, B if <code>≥ 1.5×</code>, C
          otherwise. Fill is measured from the entry side per direction — bullish FVG fills from the top down;
          bearish from the bottom up. Most retail get this nuance wrong.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT WORKS">
        <ChapterPara>
          The displacement candle ran past resting limit orders that were never filled. Market makers running
          mean-reversion books are short-gamma at gap formation — they need price to retrace to rebalance
          inventory and unwind hedges. Combined with algorithms that programmatically fade gaps, the pull is
          deterministic on most timeframes. Order book imbalance literature treats it as a measurable predictor
          of mean reversion within microstructure horizons.
        </ChapterPara>
        <ChapterPara>
          Retest probability sits around <strong>60–70%</strong> on most timeframes. The 30–40% that don't
          fill are the highest-momentum continuation moves. Unfilled FVG = continuation signal.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="fvg.ignore-overlap"
            front={<>"Any 3-candle gap counts."</>}
            back={
              <>
                If candle 1's body intrudes deep into the gap region, the imbalance is half-filled at
                formation. Bot rejects via <code>max_overlap = 0.1</code>.
              </>
            }
          />
          <FlipCard
            localStorageKey="fvg.wick-vs-body"
            front={<>"Wick into the FVG = invalidation."</>}
            back={
              <>
                Wick = mitigation. Only a body close <em>through the far edge</em> invalidates the FVG.
              </>
            }
          />
          <FlipCard
            localStorageKey="fvg.trade-all"
            front={<>"More FVGs = more entries."</>}
            back={
              <>
                Lower-TF gaps in a strong trend are continuation tells, not entries. Mode size filter exists
                exactly for this — SURGICAL accepts 0.06 ATR gaps; OVERWATCH demands 0.45.
              </>
            }
          />
          <FlipCard
            localStorageKey="fvg.bpr-confusion"
            front={<>"BPR is just a bigger FVG."</>}
            back={
              <>
                A BPR is two <em>opposite-direction</em> FVGs overlapping at the same band — both sides have
                unfinished business. Much sharper reaction than a single FVG.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>IFVG (Inversion FVG)</strong> — when price closes through an FVG in the opposite direction
            with a body, the gap flips polarity. Earliest microstructure tell of a momentum shift on the LTF.
          </li>
          <li>
            <strong>Consecutive merge</strong> — three FVGs in close succession in the same direction merge
            into one larger zone. Stacked imbalances act as one big mean-reversion magnet.
          </li>
          <li>
            <strong>News-driven gaps</strong> — less likely to fill. The imbalance was informationally driven,
            not microstructural.
          </li>
          <li>
            <strong>Decay</strong> — 5m FVG hits ~50% freshness in 8 candles (~40 min); daily FVG holds ~20
            candles. Stale FVGs are context, not entries.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

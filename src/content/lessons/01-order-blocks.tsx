import { ChartFixture, FlipCard } from '@/components/lessons/primitives';
import { ChapterPara, ChapterSection, HeroWrap, MistakeGrid } from './_shared';

export default function OrderBlocksBody() {
  return (
    <>
      <ChapterPara>
        An order block is the <strong>last opposite-color candle before a displacement that breaks structure</strong>.
        It marks where institutional inventory accepted price one final time before being forced to chase. The
        unfilled portion of the institution's book sits as resting bids (bullish OB) or offers (bearish OB) —
        a return-to-fill is mechanical, not narrative.
      </ChapterPara>

      <HeroWrap caption="Master Fixture · bullish OB lens — bearish is the mirror (same logic, swing-low side)">
        <ChartFixture lens="ob" />
      </HeroWrap>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          <strong>Bullish OB</strong> — last red/down candle before a bullish impulse that takes out the prior
          swing high. <strong>Bearish OB</strong> — last green/up candle before a bearish impulse that takes
          out the prior swing low. The zone is the candle's range — often refined to body or the 50% midpoint
          (the Consequent Encroachment).
        </ChapterPara>
        <ChapterPara>
          The bot's detector uses the LuxAlgo-style <strong>median range</strong> — tighter than the full
          candle, matches what serious traders actually mark. A parallel wick-rejection detector requires{' '}
          <code>wick/body ≥ 2.0</code> AND <code>displacement ≥ X·ATR</code>, with structure-context gating
          for Grade C blocks.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT WORKS">
        <ChapterPara>
          Institutional inventory is not filled in one print — it's sliced into iceberg child orders. The OB
          candle marks the absorption point. Price returns because (a) market makers warehoused inventory at
          the OB and need to unload partials at break-even, (b) stop-loss orders parked just beyond the OB
          extreme are the explicit liquidity target, and (c) the post-OB displacement created an FVG that
          price will reach back to rebalance.
        </ChapterPara>
        <ChapterPara>
          This is the microstructure-grounded version of Wyckoff's Composite Operator absorbing fear-driven
          sellers (bullish OB) or distributing into euphoric buyers (bearish OB).
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="ob.engulfing-mismark"
            front={<>"It's the engulfing candle."</>}
            back={
              <>
                Wrong direction. The OB is the last <em>opposite-color</em> candle <em>before</em> the
                impulse, not the impulse itself.
              </>
            }
          />
          <FlipCard
            localStorageKey="ob.no-bos"
            front={<>"Wick rejection = OB."</>}
            back={
              <>
                Without a BOS, it's just a wick. The bot enforces a structural anchor via{' '}
                <code>_has_bos_confirmation</code>.
              </>
            }
          />
          <FlipCard
            localStorageKey="ob.second-tap"
            front={<>"Second tap is the same trade."</>}
            back={
              <>
                First tap consumes unfilled inventory. Second-tap setups are statistically weaker. Treat
                mitigated OBs as context, not entries.
              </>
            }
          />
          <FlipCard
            localStorageKey="ob.wick-is-invalidation"
            front={<>"A wick into the zone invalidates it."</>}
            back={
              <>
                A wick is mitigation. Only a <strong>body close beyond the OB extreme</strong> invalidates.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>Refined vs unrefined</strong> — large-body momentum candle refines to body or 50% CE;
            small-body long-wick uses the full range.
          </li>
          <li>
            <strong>Freshness decay</strong> — half-life scales with TF (4h on 1m, 4 days on 4H, 1 week on
            Daily). A 3-week-old 5m OB has effectively zero edge.
          </li>
          <li>
            <strong>Breaker upgrade</strong> — a breaker block formed <em>after</em> a liquidity sweep is the
            highest-probability OB-family pattern.
          </li>
          <li>
            <strong>Grade-C gating</strong> — small-displacement OBs are rejected unless within 1.5·ATR of a
            recent swing.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

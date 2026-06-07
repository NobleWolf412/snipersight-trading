import { FlipCard } from '@/components/lessons/primitives';
import { WickVsCloseDemo } from '@/components/lessons/widgets';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

export default function BosChochBody() {
  return (
    <>
      <ChapterPara>
        Structure is the cleanest expression of who's in control. A <strong>BOS (Break of Structure)</strong>{' '}
        confirms the dominant cohort still has inventory to push — it's continuation. A{' '}
        <strong>CHoCH (Change of Character)</strong> confirms the opposite cohort has absorbed enough to
        reverse — it's a regime change. <strong>BOS = continuation. CHoCH = reversal.</strong> Both require a
        body close beyond the swing — wicks alone are sweeps, not breaks.
      </ChapterPara>

      <HeroWrap caption="bullish swing high shown — same wick magnitude, opposite-direction mirror for bearish swing low">
        <WickVsCloseDemo />
      </HeroWrap>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          A <strong>swing high</strong> is a 3-bar pattern where the middle bar's high exceeds both neighbors.
          A <strong>BOS</strong> fires when a candle <em>closes</em> beyond the most recent swing in the trend
          direction. A <strong>CHoCH</strong> fires when a candle closes beyond the most recent swing{' '}
          <em>against</em> the trend.
        </ChapterPara>
        <ChapterPara>
          The bot ships two detection modes. <strong>Simple mode</strong> (STRIKE, SURGICAL) is a state
          machine — fire when close clears by <code>≥ 0.5 ATR</code>. <strong>4-swing mode</strong>{' '}
          (OVERWATCH, STEALTH) demands a confirmed alternating swing sequence <code>[-1, 1, -1, 1]</code> with
          ascending levels. Slower, far fewer false breaks. Volume gating is mode-aware: OVERWATCH 1.5× avg,
          STEALTH 1.3×, STRIKE skips.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT WORKS">
        <ChapterPara>
          This is the modern restatement of Dow Theory plus Wyckoff's phase transitions: accumulation →
          markup is signaled by the first bullish CHoCH off a range low; distribution → markdown by the
          first bearish CHoCH off a range high. A wick through a swing without a close is a{' '}
          <strong>liquidity sweep</strong>, not a break — the single most important distinction in SMC
          structure.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="bos.wick-is-break"
            front={<>"Wick through = break."</>}
            back={
              <>
                Body close required. Most retail SMC indicators count wicks as breaks. The bot doesn't, and
                neither should you.
              </>
            }
          />
          <FlipCard
            localStorageKey="bos.every-pivot"
            front={<>"Every 3-bar swing matters."</>}
            back={
              <>
                On lower TFs you need higher fractal depth — bot scales <code>swing_lookback</code> per TF.
                Otherwise every candle is a swing and BOS fires constantly.
              </>
            }
          />
          <FlipCard
            localStorageKey="bos.choch-direction"
            front={<>"CHoCH means trend confirmed."</>}
            back={
              <>
                CHoCH means the trend is <em>breaking</em>. Mnemonic: BOS = continuation, CHoCH = reversal.
                CHoCH in an uptrend = turning bearish.
              </>
            }
          />
          <FlipCard
            localStorageKey="bos.single-tf"
            front={<>"Single-TF structure is enough."</>}
            back={
              <>
                A 5m CHoCH inside a 4h uptrend is a pullback opportunity, not a reversal. Bot's HTF alignment
                check (<code>_check_choch_htf_alignment</code>) enforces this discipline algorithmically.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>MSS vs CHoCH</strong> — strict ICT calls a trend reversal an MSS (Market Structure
            Shift); SMC ecosystem calls it CHoCH. Same thing, different lineage.
          </li>
          <li>
            <strong>Internal vs external structure</strong> — internal swings rotate inside the range;
            external are the range boundaries. Internal BOS is rotation; external BOS is regime change.
          </li>
          <li>
            <strong>Cycle-aware CHoCH bypass</strong> — at a confirmed DCL/WCL, bullish CHoCH is valid even
            without HTF alignment. The cycle itself is the alignment.
          </li>
          <li>
            <strong>Failed BOS</strong> — if the bullish BOS candle doesn't follow through and the next
            candle closes back below the broken swing, that's a fake breakout <em>and</em> a high-probability
            bearish CHoCH setup.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

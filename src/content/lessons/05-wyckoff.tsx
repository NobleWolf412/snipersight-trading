import { FlipCard } from '@/components/lessons/primitives';
import { WyckoffSchematic } from '@/components/lessons/widgets';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

export default function WyckoffBody() {
  return (
    <>
      <ChapterPara>
        The Wyckoff cycle describes how a single hypothetical <strong>composite operator</strong> moves price
        through four macro stages — accumulation, markup, distribution, markdown — by absorbing supply at lows
        and offloading it at highs. Each range is sub-divided into five micro-phases (A → E) marked by named
        events. The framework treats every range as a campaign with intent, not noise. Drag the playhead
        below to walk through accumulation; toggle to distribution for the mirror.
      </ChapterPara>

      <HeroWrap caption="drag the playhead — composite operator narrates intent">
        <WyckoffSchematic />
      </HeroWrap>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          <strong>Accumulation events</strong>: <code>PS</code> Preliminary Support, <code>SC</code> Selling
          Climax, <code>AR</code> Automatic Rally, <code>ST</code> Secondary Test, <code>Spring</code> (false
          breakdown below SC low), <code>Test</code>, <code>SOS</code> Sign of Strength,{' '}
          <code>LPS</code> Last Point of Support, <code>JAC</code> Jump Across the Creek.{' '}
          <strong>Distribution</strong> mirrors with PSY/BC/AR/ST/UTAD/SOW/LPSY.
        </ChapterPara>
        <ChapterPara>
          The bot's <code>cycle_detector.py</code> identifies DCL/WCL anchors. At a confirmed cycle low, the
          BOS/CHoCH detector applies a special bypass — bullish CHoCH is valid even without HTF alignment.
          The cycle itself is the alignment.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT WORKS">
        <ChapterPara>
          Institutional inventory cannot be built or sold in a single trade without moving price against the
          buyer. A campaign must span weeks because <strong>absorption is physically slow</strong>. Springs
          and UTADs exist because the last block of supply (or demand) lives in retail stop-clusters just
          outside the range; the cheapest way to harvest it is to briefly trip them.
        </ChapterPara>
        <ChapterPara>
          The structure repeats because it's a logistics problem, not psychology. Crypto is unusually
          Wyckoff-friendly: 24/7, retail-heavy, exchange-segmented liquidity. The composite-operator framing
          is more literal because a few large players genuinely dominate flow on majors.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="wyckoff.spring-always"
            front={<>"Spring always works."</>}
            back={
              <>
                A Spring that doesn't close back inside the range, or prints on rising sell volume, is{' '}
                <em>failed</em>. A real Spring needs the Test afterward on dried-up volume.
              </>
            }
          />
          <FlipCard
            localStorageKey="wyckoff.early-phase-e"
            front={<>"SOS = ready to enter."</>}
            back={
              <>
                Skipping the LPS / BU pullback is the classic chase. The pullback is what gives markup its
                low-risk entry. Wait for the retest.
              </>
            }
          />
          <FlipCard
            localStorageKey="wyckoff.reaccum-vs-dist"
            front={<>"I can tell re-accumulation from distribution mid-range."</>}
            back={
              <>
                Structurally identical until Phase C resolves. Spring-vs-UTAD outcome plus volume on the
                breakout attempt is the only reliable separator.
              </>
            }
          />
          <FlipCard
            localStorageKey="wyckoff.sc-is-bottom"
            front={<>"SC marks the bottom."</>}
            back={
              <>
                SC is where panic peaks, not where price bottoms. Final low usually prints at the Spring.
                Buying SC + stopping out at Spring is the classic retail loss pattern.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>Cause & Effect</strong> (Wyckoff's second law) — horizontal P&F count across the range
            projects how far Phase E should run. Small cause = small effect.
          </li>
          <li>
            <strong>Effort vs Result</strong> (third law) — heavy volume + narrow range = supply or demand
            being absorbed. Diagnostic for Phase B → Phase C.
          </li>
          <li>
            <strong>Crypto timeframe compression</strong> — a Phase B that took stocks 3 months can complete
            on BTC in a week. 1h/4h charts print full schematics traditional equity Wyckoff would only see
            on weeklies.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

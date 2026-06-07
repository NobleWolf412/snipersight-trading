import { FlipCard } from '@/components/lessons/primitives';
import {
  WeightSliderPanel,
  type WeightComparisonProfile,
  type WeightFactor,
} from '@/components/hud';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

// 5-factor reduced view of the bot's confluence model — pedagogical demo,
// not the live 26-factor stack. Numbers are illustrative averages; the real
// MODE_FACTOR_WEIGHTS lives in backend/strategy/confluence/scorer.py:539-694.
// SYNC: backend/strategy/confluence/scorer.py:539-694
const DEMO_FACTORS: WeightFactor[] = [
  { name: 'HTF alignment',  subScore: 0.85, baseWeight: 0.30 },
  { name: 'SMC structure',  subScore: 0.70, baseWeight: 0.25 },
  { name: 'BTC impulse',    subScore: 0.60, baseWeight: 0.20 },
  { name: 'Momentum',       subScore: 0.40, baseWeight: 0.15 },
  { name: 'Volume confirm', subScore: 0.55, baseWeight: 0.10 },
];

const MODE_PROFILES: WeightComparisonProfile[] = [
  { name: 'OVERWATCH', color: '#60a5fa', weights: { 'HTF alignment': 0.38, 'SMC structure': 0.22, 'BTC impulse': 0.18, 'Momentum': 0.10, 'Volume confirm': 0.12 } },
  { name: 'STRIKE',    color: '#f87171', weights: { 'HTF alignment': 0.18, 'SMC structure': 0.30, 'BTC impulse': 0.12, 'Momentum': 0.25, 'Volume confirm': 0.15 } },
  { name: 'SURGICAL',  color: '#fbbf24', weights: { 'HTF alignment': 0.12, 'SMC structure': 0.34, 'BTC impulse': 0.10, 'Momentum': 0.22, 'Volume confirm': 0.22 } },
  { name: 'STEALTH',   color: '#34d399', weights: { 'HTF alignment': 0.30, 'SMC structure': 0.25, 'BTC impulse': 0.20, 'Momentum': 0.15, 'Volume confirm': 0.10 } },
];

export default function ConfluenceBody() {
  return (
    <>
      <ChapterPara>
        Confluence scoring is a <strong>weighted-sum signal model</strong>: each factor emits a sub-score in
        [0, 1], a weight vector mapping factors to a composite, and a mode-specific threshold deciding pass /
        fail. The interesting failure mode is not "score too low" — it is{' '}
        <em>correlated factors voting twice</em> and{' '}
        <em>threshold passes that don't actually correspond to higher win rates</em>.
      </ChapterPara>

      <HeroWrap caption="illustrative 5-factor view · drag to explore · NOT live MODE_FACTOR_WEIGHTS">
        <WeightSliderPanel
          factors={DEMO_FACTORS}
          threshold={70}
          comparisonProfiles={MODE_PROFILES}
          thresholdLabel="STEALTH THRESHOLD"
        />
      </HeroWrap>

      <ChapterPara>
        <strong>Reading the demo</strong>: the 5 factors above are a teaching subset. The live model in{' '}
        <code>backend/strategy/confluence/scorer.py</code> uses <strong>26 factors</strong>, weights are not
        normalized (the scorer divides by sum at runtime), and the 4 mode profiles shown here are illustrative
        — not the exact <code>MODE_FACTOR_WEIGHTS</code> tables. Edit the real weights via the{' '}
        <code>/tune-confluence-weights</code> skill, never by copying these.
      </ChapterPara>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          Modern scorers layer <strong>pre-scoring gates</strong> (hard binary filters that fail-fast) on top
          of <strong>soft scoring</strong> (the weighted sum with synergy bonuses and conflict penalties).
          Gates handle nominal-scale failures (yes/no — structural anchor missing, conflict density too high);
          weights handle ordinal (more / less aligned).
        </ChapterPara>
        <ChapterPara>
          Expectancy makes the bad-weighting damage concrete:{' '}
          <code>E = (W × avgWin) − (L × avgLoss)</code>. A bad weight vector that boosts low-edge setups
          (because they ring three correlated bells) and demotes high-edge setups (signal concentrated in one
          underweighted factor) drops expectancy even as average score rises.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT WORKS — WHEN IT DOES">
        <ChapterPara>
          A weighted-sum scorer is a linear classifier in disguise. If factors are independent and each
          carries genuine predictive information, adding factors monotonically improves signal-to-noise. That's
          the Fama-French / Carhart factor-stacking premise.
        </ChapterPara>
        <ChapterPara>
          Three things break the promise: <strong>correlated factors double-count</strong>,{' '}
          <strong>more factors = more degrees of freedom = overfit</strong> (López de Prado's deflated Sharpe
          captures this rigorously), and <strong>higher threshold passes shrink the sample</strong> so the
          win-rate estimate at the new threshold is noisier than it looks.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="conf.higher-score"
            front={<>"Higher score = higher win rate."</>}
            back={
              <>
                No — higher score = higher <em>agreement among your factors</em>. If they're correlated, a
                high score reflects redundancy, not edge.
              </>
            }
          />
          <FlipCard
            localStorageKey="conf.stack-more"
            front={<>"Add a 4th oscillator for safety."</>}
            back={
              <>
                After RSI / Stoch / MACD, the 4th momentum oscillator adds zero independent signal — just
                makes momentum dominate. Diminishing returns set in fast.
              </>
            }
          />
          <FlipCard
            localStorageKey="conf.soft-compensates"
            front={<>"Soft penalties can rescue a failed gate."</>}
            back={
              <>
                They can't, and shouldn't. Failed gates mean the signal is <em>categorically</em> invalid,
                not directionally weaker.
              </>
            }
          />
          <FlipCard
            localStorageKey="conf.universal-weights"
            front={<>"One weight vector for all regimes."</>}
            back={
              <>
                Weights are regime-conditional. Same vector in trend over-weights momentum; in chop it fires
                on every retracement. That's why MODE_FACTOR_WEIGHTS exists — 4 mode profiles.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>Conflict density</strong> — multiple factors firing opposite directions = fail the
            signal, don't average. Mode-aware thresholds: 5 for OVERWATCH/macro, 3 elsewhere.
          </li>
          <li>
            <strong>Synergy bonuses</strong> — reward historically over-performing combinations. Double-edged:
            without regularization, you're memorizing past coincidences.
          </li>
          <li>
            <strong>HTF composite collapse</strong> — three mechanically-correlated HTF factors (1w / 1d /
            4h) get collapsed into one composite <em>before</em> the main weighted sum. Otherwise HTF
            mathematically dominates.
          </li>
          <li>
            <strong>Bull/bear symmetry</strong> — if shorts need score 75 but longs only 70, you have a
            structural directional bias. Either justify it with regime asymmetry or fix it. Standing fix.
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

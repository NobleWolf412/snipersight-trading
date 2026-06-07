import { FlipCard } from '@/components/lessons/primitives';
import { KillZoneClock } from '@/components/lessons/widgets';
import { ChapterPara, ChapterSection, MistakeGrid, HeroWrap } from './_shared';

export default function KillZonesBody() {
  return (
    <>
      <ChapterPara>
        Kill zones are specific intraday windows when institutional order flow concentrates — primarily{' '}
        <strong>London Open</strong>, <strong>NY AM</strong>, <strong>NY PM</strong>, and the{' '}
        <strong>London Close</strong>. Combined with the Asian range (overnight low-volatility consolidation),
        they form a daily rhythm where most volume, volatility, and liquidity-seeking moves cluster. In 24/7
        crypto these windows still matter because traditional finance desks anchor crypto liquidity to TradFi
        hours.
      </ChapterPara>

      <HeroWrap caption="NOW hand sweeps continuously; active zone highlighted">
        <KillZoneClock />
      </HeroWrap>

      <ChapterSection title="// CORE MECHANIC">
        <ChapterPara>
          Session opens carry higher volume because desks at major financial centers arrive, hedge overnight
          risk, and execute orders accumulated while their book was offline. London open is the largest forex
          injection of the day; NY open layers US equity-correlated flows on top.
        </ChapterPara>
        <ChapterPara>
          The clock above renders <strong>UTC</strong>, with arcs at the ICT-canonical windows: Asian 01:00 -
          05:00, London Open 07:00 - 10:00, NY AM 13:30 - 16:00, London Close 15:00 - 17:00, NY PM 18:30 -
          21:00. These are anchored to New York ET (EST baseline); during DST the UTC offsets shift by 1
          hour. <code>backend/strategy/smc/sessions.py</code> handles the conversion via{' '}
          <code>date-fns-tz</code> and the <code>America/New_York</code> zone — never hard-code <code>±5</code>
          {' '}or <code>±4</code>.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// WHY IT WORKS — IN CRYPTO">
        <ChapterPara>
          Crypto isn't structurally tied to TradFi hours, but empirically Bitcoin volume and realized
          volatility peak during US / EU business hours. The Asia gap between NY close (~17:00 ET) and Tokyo
          open (~19:00 ET) is consistently the quietest period. Periodicity studies confirm the pattern at
          statistically significant magnitudes.
        </ChapterPara>
        <ChapterPara>
          Liquidity grabs cluster at session boundaries. The most reliable sweep targets on BTC/ETH are
          previous-day high / low, previous-week high / low, and the Asian-range extremes — all raided in
          the first hour of London or NY. This is the mechanical reason kill zones produce reversals, not
          just breakouts.
        </ChapterPara>
      </ChapterSection>

      <ChapterSection title="// COMMON MISTAKES">
        <MistakeGrid>
          <FlipCard
            localStorageKey="kz.gmt"
            front={<>"Kill zone times are GMT."</>}
            back={
              <>
                Wrong reference frame. ICT defines them in <strong>New York ET</strong>. Local equivalents
                drift twice a year as US and UK DST schedules diverge.
              </>
            }
          />
          <FlipCard
            localStorageKey="kz.volume-entries"
            front={<>"Highest volume = best entries."</>}
            back={
              <>
                Highest volume usually means widest stops are required. Kill zones produce{' '}
                <em>opportunities</em>, not certainties. Without confluence, an entry inside one is just
                higher volatility.
              </>
            }
          />
          <FlipCard
            localStorageKey="kz.london-breakout"
            front={<>"London Open = London breakout."</>}
            back={
              <>
                Classic London behavior is <em>first</em> to sweep the Asian-range high or low (Judas swing),
                then reverse. Naive breakout entries get caught.
              </>
            }
          />
          <FlipCard
            localStorageKey="kz.crypto-247"
            front={<>"Crypto is 24/7 — TradFi hours don't matter."</>}
            back={
              <>
                Empirically false. Volume and volatility peak during US / EU business hours; the Asia gap is
                consistently the quietest period.
              </>
            }
          />
        </MistakeGrid>
      </ChapterSection>

      <ChapterSection title="// EDGE CASES">
        <ul className="lesson-bullets">
          <li>
            <strong>CME 24/7 (2026-05-29)</strong> — CME Bitcoin futures moved to 24/7 trading. The
            weekend-gap era ended. Historically Friday-Sunday CME closes created predictable Monday gaps that
            filled ~70-80% of the time. Cite as historical context only.
          </li>
          <li>
            <strong>Funding-rate timing on perps</strong> — Phemex settles every 8 hours on a UTC 00:00 /
            08:00 / 16:00 clock. Funding flips don't coincide with kill zones but create their own
            micro-volatility spikes.
          </li>
          <li>
            <strong>Day-of-week effects</strong> — Monday opens absorb weekend news; Friday late-NY drifts on
            position closing; Tue-Thu is typically the highest-conviction window.
          </li>
          <li>
            <strong>JPY and Asia-domiciled alts</strong> — Asian session is the primary window for those
            pairs, not a "dead session".
          </li>
        </ul>
      </ChapterSection>
    </>
  );
}

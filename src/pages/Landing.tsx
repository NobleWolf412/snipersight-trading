import { Link } from 'react-router-dom';
import snipersightLogo from '../assets/images/1000016768.png';
import './Landing.css';

const tools = [
  { to: '/intel', title: 'Market context', text: 'Regime, mode advice, sessions and funding, with freshness and availability.' },
  { to: '/bot', title: 'Session control', text: 'Separate paper, testnet and live execution. Review risk and monitor attention.' },
  { to: '/journal', title: 'Execution records', text: 'Inspect completed trades, filter records and export the journal.' },
  { to: '/training', title: 'Learning and research', text: 'Read strategy chapters, explore historical candles or configure a paper session.' },
];

export function Landing() {
  return <div className="landing-intro">
    <section className="landing-intro__hero">
      <img src={snipersightLogo} alt="SniperSight" width="360" height="120" />
      <p className="mono">Smart Money Concepts trading intelligence</p>
      <h1>Read the setup.<br />Check the evidence.</h1>
      <p>Scan across timeframes, inspect the evidence and review a trade plan.
        Every rejection has a reason. Execution requires a separately configured session.</p>
      <Link className="btn btn-cyan" to="/scanner">Open scanner →</Link>
      <p className="landing-intro__note">Scores rank evidence. They are not win probabilities.</p>
    </section>
    <section className="landing-intro__example" aria-labelledby="example-title">
      <div className="landing-intro__example-head">
        <h2 id="example-title">Example setup</h2><span className="chip">STATIC EXAMPLE</span>
      </div>
      <p>Illustrative values only. This is not a current signal or an execution record.</p>
      <dl>
        <div><dt>Symbol</dt><dd>SOL/USDT</dd></div>
        <div><dt>Direction</dt><dd>LONG</dd></div>
        <div><dt>Evidence score</dt><dd>74 / 100</dd></div>
        <div><dt>Setup</dt><dd>Liquidity sweep and reclaim</dd></div>
      </dl>
      <p>The scanner shows recorded entry, stop, targets, source and rejection evidence.
        Unknown values remain unavailable.</p>
    </section>
    <nav className="landing-intro__tools" aria-label="Explore SniperSight">
      {tools.map(tool => <Link key={tool.to} to={tool.to}>
        <h2>{tool.title} <span aria-hidden="true">→</span></h2><p>{tool.text}</p>
      </Link>)}
    </nav>
  </div>;
}

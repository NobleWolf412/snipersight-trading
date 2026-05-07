// ── SniperSight LANDING ───────────────────────────────────
// (useState/useEffect/useRef already declared by shared.jsx)

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "page",
  "density": "balanced",
  "tacticalBg": true,
  "hudOverlays": true,
  "simSpeed": 1,
  "heroVariant": "scope",
  "tagline": "See the market before it moves."
}/*EDITMODE-END*/;

const PAGE_ACCENT = 'amber';

// ── Live tickers (fake but believable) ─────────────────────
const TICKERS = [
  {sym:'BTCUSDT', p:67841.20, c:+1.42},
  {sym:'ETHUSDT', p:3284.55, c:+2.18},
  {sym:'SOLUSDT', p:178.34, c:+4.62},
  {sym:'BNBUSDT', p:612.40, c:+0.88},
  {sym:'XRPUSDT', p:0.5184, c:-0.42},
  {sym:'DOGEUSDT', p:0.1622, c:+3.14},
  {sym:'AVAXUSDT', p:38.91, c:+2.04},
  {sym:'LINKUSDT', p:14.82, c:+1.66},
  {sym:'ARBUSDT', p:0.8912, c:-1.18},
  {sym:'SUIUSDT', p:1.482, c:+5.84},
  {sym:'TIAUSDT', p:5.124, c:+3.92},
  {sym:'INJUSDT', p:24.18, c:+1.04},
];

// ── Animated SCOPE (the hero centerpiece) ──────────────────
function Scope(){
  const [t,setT] = useState(0);
  useEffect(()=>{ const id = setInterval(()=>setT(x=>x+1), 60); return ()=>clearInterval(id); },[]);
  // generate candle data
  const candles = useRef(Array.from({length:48},(_,i)=>{
    const base = 50 + Math.sin(i*0.4)*8 + i*0.3;
    const o = base + (Math.random()-.5)*3;
    const c = base + (Math.random()-.5)*4;
    const h = Math.max(o,c) + Math.random()*2;
    const l = Math.min(o,c) - Math.random()*2;
    return {o,h,l,c};
  })).current;
  // sweeping locks
  const lockX = 50 + Math.sin(t*0.04)*20;
  const lockY = 50 + Math.cos(t*0.05)*15;

  return (
    <div className="scope-wrap">
      {/* glowing ring */}
      <svg viewBox="-100 -100 200 200" className="scope-svg">
        <defs>
          <radialGradient id="scopeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity=".15"/>
            <stop offset="60%" stopColor="var(--accent)" stopOpacity=".04"/>
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="1.4"/>
          </filter>
        </defs>
        <circle r="92" fill="url(#scopeGlow)"/>
        {/* outer rotating ring */}
        <g style={{transform:`rotate(${t*0.4}deg)`,transformOrigin:'center'}}>
          <circle r="86" fill="none" stroke="var(--accent)" strokeOpacity=".5" strokeWidth=".5" strokeDasharray="2 6"/>
          {[0,60,120,180,240,300].map(a=>(
            <line key={a} x1={Math.cos(a*Math.PI/180)*82} y1={Math.sin(a*Math.PI/180)*82} x2={Math.cos(a*Math.PI/180)*90} y2={Math.sin(a*Math.PI/180)*90} stroke="var(--accent)" strokeWidth="1"/>
          ))}
        </g>
        {/* mid ring */}
        <g style={{transform:`rotate(${-t*0.6}deg)`,transformOrigin:'center'}}>
          <circle r="68" fill="none" stroke="var(--accent)" strokeOpacity=".7" strokeWidth=".6"/>
          {Array.from({length:36}).map((_,i)=>(
            <line key={i} x1={Math.cos(i*10*Math.PI/180)*64} y1={Math.sin(i*10*Math.PI/180)*64} x2={Math.cos(i*10*Math.PI/180)*68} y2={Math.sin(i*10*Math.PI/180)*68} stroke="var(--accent)" strokeOpacity={i%3===0?.8:.3} strokeWidth=".5"/>
          ))}
        </g>
        {/* crosshairs */}
        <line x1="-92" y1="0" x2="-50" y2="0" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7"/>
        <line x1="50" y1="0" x2="92" y2="0" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7"/>
        <line x1="0" y1="-92" x2="0" y2="-50" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7"/>
        <line x1="0" y1="50" x2="0" y2="92" stroke="var(--accent)" strokeWidth=".8" strokeOpacity=".7"/>
        {/* candles arc */}
        <g>
          {candles.map((c,i)=>{
            const ang = -90 + (i/(candles.length-1))*180;
            const r1 = 32, r2 = 44;
            const radius = r1 + ((c.h-c.l)/8)*(r2-r1);
            const cx = Math.cos(ang*Math.PI/180)*38;
            const cy = Math.sin(ang*Math.PI/180)*38;
            const bullish = c.c>=c.o;
            return (
              <g key={i} style={{transform:`rotate(${ang+90}deg) translate(0,-38px)`,transformOrigin:'center'}}>
                <line x1="0" y1="-6" x2="0" y2="6" stroke={bullish?'var(--green-soft)':'var(--red-2)'} strokeOpacity=".6" strokeWidth=".4"/>
                <rect x="-1.4" y={bullish?-3:0} width="2.8" height="3" fill={bullish?'var(--green-soft)':'var(--red-2)'} fillOpacity=".85"/>
              </g>
            );
          })}
        </g>
        {/* center reticle */}
        <circle r="22" fill="none" stroke="var(--accent)" strokeOpacity=".9" strokeWidth=".8"/>
        <circle r="3" fill="var(--accent)" filter="url(#glow)"/>
        <line x1="-22" y1="0" x2="-8" y2="0" stroke="var(--accent)" strokeWidth=".8"/>
        <line x1="8" y1="0" x2="22" y2="0" stroke="var(--accent)" strokeWidth=".8"/>
        <line x1="0" y1="-22" x2="0" y2="-8" stroke="var(--accent)" strokeWidth=".8"/>
        <line x1="0" y1="8" x2="0" y2="22" stroke="var(--accent)" strokeWidth=".8"/>
        {/* scanning lock */}
        <g style={{transform:`translate(${lockX-50}%, ${lockY-50}%)`}}>
          <rect x="-8" y="-8" width="16" height="16" fill="none" stroke="var(--accent)" strokeWidth="1" opacity={(Math.sin(t*0.3)+1)/2*.6+.4}/>
        </g>
        {/* labels */}
        <text x="-86" y="-86" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">[ TGT-LOCK ]</text>
        <text x="48" y="-86" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">{('00'+(t%999)).slice(-3)}</text>
        <text x="-86" y="92" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">SCAN-MODE</text>
        <text x="60" y="92" fill="var(--accent)" opacity=".7" fontSize="6" fontFamily="Share Tech Mono">{(60+Math.sin(t*0.1)*3).toFixed(1)}Hz</text>
      </svg>
      {/* HUD readouts overlay */}
      <div className="scope-hud-tl">
        <div className="mono" style={{fontSize:9,color:'var(--accent)',letterSpacing:'.2em'}}>// FEED</div>
        <div className="mono" style={{fontSize:11,color:'var(--fg)'}}>BTC ${(67841 + Math.sin(t*0.2)*40).toFixed(2)}</div>
        <div className="mono" style={{fontSize:9,color:'var(--green-soft)'}}>+1.42% / 1H</div>
      </div>
      <div className="scope-hud-tr">
        <div className="mono" style={{fontSize:9,color:'var(--accent)',letterSpacing:'.2em'}}>// DELTA</div>
        <div className="mono" style={{fontSize:11,color:'var(--green-soft)'}}>BUY {(58.2+Math.sin(t*0.1)*4).toFixed(1)}%</div>
        <div className="mono" style={{fontSize:9,color:'var(--red-2)'}}>SELL {(41.8-Math.sin(t*0.1)*4).toFixed(1)}%</div>
      </div>
      <div className="scope-hud-bl">
        <div className="mono" style={{fontSize:9,color:'var(--accent)',letterSpacing:'.2em'}}>// REGIME</div>
        <div className="mono" style={{fontSize:11,color:'var(--fg)'}}>RISK-ON</div>
        <div className="mono" style={{fontSize:9,color:'var(--fg-3)'}}>VIX 14.2 · DXY 104.8</div>
      </div>
      <div className="scope-hud-br">
        <div className="mono" style={{fontSize:9,color:'var(--accent)',letterSpacing:'.2em'}}>// SIGNAL</div>
        <div className="mono" style={{fontSize:11,color:'var(--green-soft)'}}>● ARMED</div>
        <div className="mono" style={{fontSize:9,color:'var(--fg-3)'}}>conf 82% · A-grade</div>
      </div>
    </div>
  );
}

// ── Live ticker rail ───────────────────────────────────────
function TickerRail(){
  const [t,setT] = useState(0);
  useEffect(()=>{ const id=setInterval(()=>setT(x=>x+1),1500); return ()=>clearInterval(id); },[]);
  return (
    <div className="ticker-rail">
      <div className="ticker-track">
        {[...TICKERS,...TICKERS].map((tk,i)=>{
          const drift = Math.sin((t+i)*0.4)*0.3;
          const c = tk.c + drift;
          return (
            <div key={i} className="ticker-item">
              <span className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.1em'}}>{tk.sym.replace('USDT','/USDT')}</span>
              <span className="mono" style={{fontSize:11,color:'var(--fg)',fontWeight:600}}>${tk.p.toFixed(tk.p<1?4:2)}</span>
              <span className="mono" style={{fontSize:10,color:c>=0?'var(--green-soft)':'var(--red-2)'}}>{c>=0?'▲':'▼'} {Math.abs(c).toFixed(2)}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Feature card ──────────────────────────────────────────
function FeatureCard({ icon, title, body, href, accent }){
  return (
    <a href={href} className="feat-card" style={{textDecoration:'none',color:'inherit'}}>
      <div className="feat-icon" style={{color:accent}}>{icon}</div>
      <div className="feat-title">{title}</div>
      <div className="feat-body">{body}</div>
      <div className="feat-cta mono" style={{color:accent}}>ENTER →</div>
      <div className="feat-deco">
        <svg viewBox="0 0 100 100" width="100%" height="100%">
          <circle cx="50" cy="50" r="44" fill="none" stroke={accent} strokeOpacity=".15" strokeWidth=".5" strokeDasharray="2 4"/>
          <circle cx="50" cy="50" r="30" fill="none" stroke={accent} strokeOpacity=".1" strokeWidth=".5"/>
        </svg>
      </div>
    </a>
  );
}

// ── Sample signal card (proof) ────────────────────────────
function SignalProof({ sym, side, price, conf, setup, change }){
  const long = side==='LONG';
  return (
    <div className="proof-signal">
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
        <span className="mono" style={{fontSize:11,color:'var(--fg)',letterSpacing:'.05em',fontWeight:700}}>{sym}</span>
        <span className={`chip ${long?'chip-green':'chip-red'}`} style={{fontSize:9}}>{long?'▲ LONG':'▼ SHORT'}</span>
      </div>
      <div style={{display:'flex',alignItems:'baseline',gap:10,marginBottom:8}}>
        <span className="mono" style={{fontSize:16,color:'var(--accent)',fontWeight:700}}>${price}</span>
        <span className="mono" style={{fontSize:10,color:change>=0?'var(--green-soft)':'var(--red-2)'}}>{change>=0?'+':''}{change}%</span>
      </div>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <span className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.14em',textTransform:'uppercase'}}>{setup}</span>
        <span className="mono" style={{fontSize:10,color:'var(--accent)',fontWeight:700}}>{conf}%</span>
      </div>
      <div style={{height:4,background:'rgba(0,0,0,.5)',borderRadius:2,marginTop:6,overflow:'hidden'}}>
        <div style={{width:conf+'%',height:'100%',background:'var(--accent)',boxShadow:`0 0 8px var(--accent)`}}/>
      </div>
    </div>
  );
}

function App(){
  const [t, setTweak] = window.useTweaks ? window.useTweaks(TWEAK_DEFAULTS) : [TWEAK_DEFAULTS,()=>{}];
  const [now,setNow] = useState(Date.now());
  useEffect(()=>{ window.SS.applyTweaks(t, PAGE_ACCENT); },[t]);
  useEffect(()=>{ const id = setInterval(()=>setNow(Date.now()), 1000); return ()=>clearInterval(id); },[]);

  const TweaksPanel = window.TweaksPanel;

  return (
    <div className="landing-shell">
      {/* Top minimal bar */}
      <div className="land-topbar">
        <div className="brand" style={{textDecoration:'none',color:'inherit'}}>
          <img src="logo.png" alt="SniperSight" className="brand-logo-img"/>
        </div>
        <div style={{display:'flex',gap:8,alignItems:'center'}}>
          <span className="chip chip-green">● 4 NODES ONLINE</span>
          <span className="chip mono">v1.0.0</span>
          <a href="Bot Status.html" className="btn btn-amber" style={{textDecoration:'none',padding:'8px 14px',fontSize:11,fontWeight:700,letterSpacing:'.18em'}}>LAUNCH HUD →</a>
        </div>
      </div>

      <TickerRail/>

      {/* HERO */}
      <section className="hero">
        <div className="hero-left">
          <div className="hero-eyebrow mono">
            <span style={{color:'var(--accent)'}}>●</span> SYSTEM-ONLINE · v1.0 · TACTICAL TRADING TERMINAL
          </div>
          <h1 className="hero-title">
            See the market<br/>
            <span className="hero-title-em">before it moves.</span>
          </h1>
          <p className="hero-sub">
            SniperSight is a tactical heads-up display for crypto. Six purpose-built consoles fuse on-chain flow, derivatives positioning, and price action into one calm signal — then automate the trade end-to-end.
          </p>
          <div className="hero-stats">
            <div><div className="hero-stat-v mono">61.4<span style={{color:'var(--accent)'}}>%</span></div><div className="hero-stat-l mono">win rate · 60d</div></div>
            <div className="hero-stat-sep"/>
            <div><div className="hero-stat-v mono">+0.84<span style={{color:'var(--accent)'}}>R</span></div><div className="hero-stat-l mono">avg per trade</div></div>
            <div className="hero-stat-sep"/>
            <div><div className="hero-stat-v mono">2.1<span style={{color:'var(--accent)'}}>s</span></div><div className="hero-stat-l mono">sig→entry latency</div></div>
            <div className="hero-stat-sep"/>
            <div><div className="hero-stat-v mono">412<span style={{color:'var(--accent)'}}>k</span></div><div className="hero-stat-l mono">candles scanned/d</div></div>
          </div>
          <div className="hero-cta">
            <a href="Bot.html" className="btn-mega">
              <span>▶ ENTER COMMAND HUB</span>
              <span className="mono" style={{fontSize:9,letterSpacing:'.2em',opacity:.7,marginTop:2}}>CONFIGURE & DEPLOY THE BOT</span>
            </a>
            <a href="Training.html" className="btn-mega btn-mega-ghost">
              <span>◇ TRAINING GROUND</span>
              <span className="mono" style={{fontSize:9,letterSpacing:'.2em',opacity:.7,marginTop:2}}>RANGE · DRILLS · REPLAY</span>
            </a>
          </div>
          <div className="hero-foot mono">
            <span>● BINANCE</span><span style={{color:'var(--fg-4)'}}>·</span>
            <span>● PHEMEX</span><span style={{color:'var(--fg-4)'}}>·</span>
            <span>● BYBIT</span><span style={{color:'var(--fg-4)'}}>·</span>
            <span>● BINGX</span><span style={{color:'var(--fg-4)'}}>·</span>
            <span style={{color:'var(--fg-3)'}}>4 venue execution router</span>
          </div>
        </div>
        <div className="hero-right">
          <Scope/>
        </div>
      </section>

      {/* MODULES GRID */}
      <section className="modules">
        <div className="sec-title-row">
          <div className="sec-title-line"/>
          <div className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.3em',textTransform:'uppercase'}}>// SIX CONSOLES · ONE NETWORK</div>
          <div className="sec-title-line"/>
        </div>
        <div className="modules-grid">
          <FeatureCard
            href="Intel.html"
            accent="#60a5fa"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5"/><path d="M3 16h26M16 3a18 18 0 0 1 0 26M16 3a18 18 0 0 0 0 26" stroke="currentColor" strokeWidth="1"/></svg>}
            title="Intel"
            body="BTC dominance, market regime, liquidations, funding skew, news desk and AI macro commentary — the chart-room view of where the whole market sits right now."
          />
          <FeatureCard
            href="Scanner.html"
            accent="#fbbf24"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="14" cy="14" r="9" stroke="currentColor" strokeWidth="1.5"/><path d="M21 21l7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/><circle cx="14" cy="14" r="3" fill="currentColor"/></svg>}
            title="Scanner"
            body="Continuous radar across 412 symbols. Detects breakouts, range fakes, liquidity sweeps and reclaim setups; ranks every signal A→D with conviction scoring."
          />
          <FeatureCard
            href="Bot Status.html"
            accent="#f87171"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="6" y="6" width="20" height="20" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M11 16l4 4 6-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/><circle cx="16" cy="2" r="2" fill="currentColor"/></svg>}
            title="Bot Status"
            body="Live command center: armed positions, R-multiples ticking, kill-switch armed, full execution log. The room you sit in while the bot is hot."
          />
          <FeatureCard
            href="Journal.html"
            accent="#4ade80"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M6 6h20v20H6z" stroke="currentColor" strokeWidth="1.5"/><path d="M10 12h12M10 16h12M10 20h8" stroke="currentColor" strokeWidth="1.5"/></svg>}
            title="Journal"
            body="Every trade autopsied: equity curve, MAE/MFE, per-symbol edge, per-setup edge, time-of-day bias, drawdown, tags. Then trains the next iteration of the model."
          />
          <FeatureCard
            href="Training.html"
            accent="#22d3ee"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="3" fill="currentColor"/><circle cx="16" cy="16" r="9" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2"/><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5"/></svg>}
            title="Training"
            body="Drill room. Replay historical setups, run the autonomous paper-bot on simulated capital, ace the pattern quizzes. Build conviction before risking a dollar."
          />
          <FeatureCard
            href="Bot Setup.html"
            accent="#c084fc"
            icon={<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="4" stroke="currentColor" strokeWidth="1.5"/><path d="M16 4v4M16 24v4M4 16h4M24 16h4M7 7l3 3M22 22l3 3M7 25l3-3M22 10l3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>}
            title="Setup"
            body="Calibrate the strategy: timeframe stack, conviction floor, risk-per-trade, leverage cap, exchange routing, kill conditions. Ship it once, tune it forever."
          />
        </div>
      </section>

      {/* PROOF STRIP */}
      <section className="proof">
        <div className="proof-left">
          <div className="mono" style={{fontSize:10,color:'var(--accent)',letterSpacing:'.3em',marginBottom:14}}>// LIVE-FEED // SAMPLE-SIGNALS</div>
          <h2 className="proof-h">Calm under fire.</h2>
          <p className="proof-p">
            The HUD never panics. It scores conviction, sizes risk, fires the entry, parks the stop, drags the trail, and posts a clean line in the journal. You watch it work — or you walk away.
          </p>
          <div className="proof-bullets">
            <div><span className="mono" style={{color:'var(--accent)'}}>›</span> Signal-grade gating: only A/B trades fire</div>
            <div><span className="mono" style={{color:'var(--accent)'}}>›</span> Hard daily-loss kill switch · armed at boot</div>
            <div><span className="mono" style={{color:'var(--accent)'}}>›</span> Per-venue position sync · zero drift</div>
            <div><span className="mono" style={{color:'var(--accent)'}}>›</span> Telegram + audio + on-screen alerts</div>
            <div><span className="mono" style={{color:'var(--accent)'}}>›</span> Backtest harness over 2y of 1m data</div>
          </div>
          <a href="Scanner.html" className="btn btn-amber" style={{textDecoration:'none',padding:'12px 20px',fontSize:12,fontWeight:700,letterSpacing:'.2em',display:'inline-block',marginTop:18}}>EXPLORE SIGNALS →</a>
        </div>
        <div className="proof-right">
          <div className="proof-feed-head">
            <span className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.2em'}}>▣ LIVE SIGNAL FEED</span>
            <span className="chip chip-green" style={{fontSize:9}}>● STREAMING</span>
          </div>
          <div className="proof-grid">
            <SignalProof sym="SOL/USDT" side="LONG" price="178.34" conf={87} setup="LIQ-SWEEP-RECLAIM" change={4.62}/>
            <SignalProof sym="ETH/USDT" side="LONG" price="3284.55" conf={82} setup="RANGE-BREAK · 4H" change={2.18}/>
            <SignalProof sym="ARB/USDT" side="SHORT" price="0.8912" conf={74} setup="LH · TREND-REJ" change={-1.18}/>
            <SignalProof sym="SUI/USDT" side="LONG" price="1.482" conf={91} setup="CONSOL · BREAK" change={5.84}/>
            <SignalProof sym="TIA/USDT" side="LONG" price="5.124" conf={78} setup="VOL-EXPANSION" change={3.92}/>
            <SignalProof sym="BNB/USDT" side="LONG" price="612.40" conf={68} setup="VWAP-RECLAIM" change={0.88}/>
          </div>
        </div>
      </section>

      {/* OPERATING DOCTRINE */}
      <section className="doctrine">
        <div className="sec-title-row">
          <div className="sec-title-line"/>
          <div className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.3em',textTransform:'uppercase'}}>// OPERATING DOCTRINE</div>
          <div className="sec-title-line"/>
        </div>
        <div className="doctrine-grid">
          <div className="doctrine-card">
            <div className="doctrine-num mono">01</div>
            <div className="doctrine-h">Observe</div>
            <div className="doctrine-b">Intel watches the macro tide. Scanner watches every symbol. Nothing is missed; nothing is rushed.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">02</div>
            <div className="doctrine-h">Score</div>
            <div className="doctrine-b">Each setup is graded A/B/C/D. Only A/B trades arm. Conviction gates the trigger.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">03</div>
            <div className="doctrine-h">Execute</div>
            <div className="doctrine-b">Bot sizes, fires, places stop and trail. You watch the R climb on the HUD or sleep through it.</div>
          </div>
          <div className="doctrine-arrow">→</div>
          <div className="doctrine-card">
            <div className="doctrine-num mono">04</div>
            <div className="doctrine-h">Learn</div>
            <div className="doctrine-b">Journal autopsies every fill. Model retrains on closed trades. Edge compounds.</div>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="cta-final">
        <div className="cta-final-bg">
          <svg viewBox="0 0 800 200" preserveAspectRatio="none" width="100%" height="100%">
            <defs>
              <linearGradient id="ctaG" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity=".06"/>
                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
              </linearGradient>
            </defs>
            <rect width="800" height="200" fill="url(#ctaG)"/>
            {Array.from({length:30}).map((_,i)=>(
              <line key={i} x1={i*30} y1="0" x2={i*30} y2="200" stroke="var(--accent)" strokeOpacity=".05" strokeWidth=".5"/>
            ))}
          </svg>
        </div>
        <div className="cta-final-inner">
          <div className="mono" style={{fontSize:10,color:'var(--accent)',letterSpacing:'.4em',marginBottom:14}}>// READY-TO-DEPLOY</div>
          <h2 className="cta-final-h">Let the bot do the watching.</h2>
          <p className="cta-final-p">Six consoles. One network. The market on a leash.</p>
          <div className="cta-final-btns">
            <a href="Bot Status.html" className="btn-mega">
              <span>▶ LAUNCH HUD</span>
              <span className="mono" style={{fontSize:9,letterSpacing:'.2em',opacity:.7,marginTop:2}}>ENTER COMMAND CENTER</span>
            </a>
            <a href="Training.html" className="btn-mega btn-mega-ghost">
              <span>◇ START TRAINING</span>
              <span className="mono" style={{fontSize:9,letterSpacing:'.2em',opacity:.7,marginTop:2}}>SAFE SANDBOX</span>
            </a>
          </div>
        </div>
      </section>

      <footer className="land-footer">
        <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>build 1.0.0+5cdb504 · all systems nominal</div>
        <div style={{display:'flex',gap:14,flexWrap:'wrap'}}>
          <a href="Intel.html" style={{color:'var(--fg-3)',textDecoration:'none',fontSize:11}}>Intel</a>
          <a href="Scanner.html" style={{color:'var(--fg-3)',textDecoration:'none',fontSize:11}}>Scanner</a>
          <a href="Bot Status.html" style={{color:'var(--fg-3)',textDecoration:'none',fontSize:11}}>Bot Status</a>
          <a href="Journal.html" style={{color:'var(--fg-3)',textDecoration:'none',fontSize:11}}>Journal</a>
          <a href="Training.html" style={{color:'var(--fg-3)',textDecoration:'none',fontSize:11}}>Training</a>
          <a href="Bot Setup.html" style={{color:'var(--fg-3)',textDecoration:'none',fontSize:11}}>Setup</a>
        </div>
        <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em'}}>SniperSight HUD · {new Date(now).toUTCString().slice(17,25)} UTC</div>
      </footer>

      {TweaksPanel && <TweaksPanel title="Tweaks">
        <window.SS.SharedTweaksControls t={t} setTweak={setTweak}/>
      </TweaksPanel>}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

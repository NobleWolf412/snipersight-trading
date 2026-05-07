const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ── Sample data ─────────────────────────────────────────────
const SEED_POSITIONS = [
  {
    id: 'p1', symbol: 'BTC/USDT', direction: 'LONG', trade_type: 'swing',
    entry_price: 64280.50, current_price: 65120.25, stop_loss: 63450, initial_stop_loss: 63450,
    tp1: 65800, tp2: 66600, tp_final: 67900,
    quantity: 0.0312, unrealized_pnl: 26.20, unrealized_pnl_pct: 1.31,
    target_pnl: 47.30, risk_pnl: -25.85,
    targets_hit: 0, targets_remaining: 3,
    breakeven_active: false, trailing_active: false,
    opened_at: Date.now() - 1000 * 60 * 47,
    confluence: 8.2, leverage: 5,
  },
  {
    id: 'p2', symbol: 'ETH/USDT', direction: 'LONG', trade_type: 'intraday',
    entry_price: 3214.80, current_price: 3198.40, stop_loss: 3168, initial_stop_loss: 3168,
    tp1: 3260, tp2: 3305, tp_final: 3360,
    quantity: 0.62, unrealized_pnl: -10.17, unrealized_pnl_pct: -0.51,
    target_pnl: 28.04, risk_pnl: -29.02,
    targets_hit: 0, targets_remaining: 3,
    breakeven_active: false, trailing_active: false,
    opened_at: Date.now() - 1000 * 60 * 22,
    confluence: 7.4, leverage: 3,
  },
  {
    id: 'p3', symbol: 'SOL/USDT', direction: 'SHORT', trade_type: 'scalp',
    entry_price: 143.82, current_price: 141.05, stop_loss: 145.40, initial_stop_loss: 146.10,
    tp1: 141.20, tp2: 139.40, tp_final: 137.00,
    quantity: 6.8, unrealized_pnl: 18.84, unrealized_pnl_pct: 1.93,
    target_pnl: 22.40, risk_pnl: -10.74,
    targets_hit: 1, targets_remaining: 2,
    breakeven_active: true, trailing_active: false,
    opened_at: Date.now() - 1000 * 60 * 11,
    confluence: 7.8, leverage: 8,
  },
];

const SEED_HISTORY = [
  { id:'t1', symbol:'AVAX/USDT', direction:'LONG',  trade_type:'intraday', entry_price:34.420, exit_price:35.180, pnl:23.18, pnl_pct:2.21, exit_reason:'tp2_hit',       entry_time: Date.now()-1000*60*180, exit_time: Date.now()-1000*60*132, max_favorable:2.45, max_adverse:0.32, quantity:30.4, targets_hit:[1,1], confidence_score:81 },
  { id:'t2', symbol:'LINK/USDT', direction:'SHORT', trade_type:'scalp',    entry_price:14.860, exit_price:14.620, pnl:11.40, pnl_pct:1.61, exit_reason:'tp1_hit',       entry_time: Date.now()-1000*60*240, exit_time: Date.now()-1000*60*222, max_favorable:1.71, max_adverse:0.18, quantity:47.5, targets_hit:[1],   confidence_score:74 },
  { id:'t3', symbol:'DOGE/USDT', direction:'LONG',  trade_type:'scalp',    entry_price:0.13420,exit_price:0.13290,pnl:-6.20, pnl_pct:-0.97,exit_reason:'stop_loss',     entry_time: Date.now()-1000*60*310, exit_time: Date.now()-1000*60*286, max_favorable:.42, max_adverse:1.10, quantity:480,   targets_hit:[],    confidence_score:69 },
  { id:'t4', symbol:'ARB/USDT',  direction:'LONG',  trade_type:'swing',    entry_price:1.0820, exit_price:1.1130, pnl:18.60, pnl_pct:2.86, exit_reason:'trailing_stop', entry_time: Date.now()-1000*60*420, exit_time: Date.now()-1000*60*330, max_favorable:3.12, max_adverse:0.51, quantity:600,   targets_hit:[1,1], confidence_score:79 },
  { id:'t5', symbol:'BNB/USDT',  direction:'SHORT', trade_type:'intraday', entry_price:572.40, exit_price:570.10, pnl:5.10,  pnl_pct:0.40, exit_reason:'breakeven_stop',entry_time: Date.now()-1000*60*505, exit_time: Date.now()-1000*60*460, max_favorable:.92, max_adverse:0.21, quantity:2.2,   targets_hit:[],    confidence_score:71 },
  { id:'t6', symbol:'INJ/USDT',  direction:'LONG',  trade_type:'intraday', entry_price:24.180, exit_price:24.760, pnl:14.92, pnl_pct:2.40, exit_reason:'tp1_hit',       entry_time: Date.now()-1000*60*620, exit_time: Date.now()-1000*60*580, max_favorable:2.62, max_adverse:0.41, quantity:25.7,  targets_hit:[1],   confidence_score:76 },
];

const SEED_WATCHLIST = [
  { symbol:'BTC/USDT', score: 8.2, last: 65120.25, change: 1.42, htf:'BULL', regime:'TREND',  status:'ARMED' },
  { symbol:'ETH/USDT', score: 7.4, last: 3198.40,  change: -.32, htf:'BULL', regime:'TREND',  status:'ARMED' },
  { symbol:'SOL/USDT', score: 7.8, last: 141.05,   change:  .81, htf:'BEAR', regime:'RANGE',  status:'ARMED' },
  { symbol:'TIA/USDT', score: 6.9, last: 6.842,    change: 2.10, htf:'BULL', regime:'TREND',  status:'WATCH' },
  { symbol:'AAVE/USDT',score: 6.1, last: 92.18,    change: -.45, htf:'NEUT', regime:'RANGE',  status:'WATCH' },
  { symbol:'OP/USDT',  score: 5.8, last: 1.892,    change: -.91, htf:'BEAR', regime:'RANGE',  status:'WATCH' },
  { symbol:'NEAR/USDT',score: 5.2, last: 4.310,    change:  .12, htf:'NEUT', regime:'CHOP',   status:'COLD' },
];

const SCAN_SYMBOLS = ['BTC','ETH','SOL','BNB','XRP','TON','AVAX','TIA','LINK','DOGE','SHIB','ADA','APT','SUI','SEI','OP','ARB','INJ','RNDR','PEPE','NEAR','AAVE','LDO','ATOM','PENDLE'];

function fmtMoney(v, d=2){ return (v<0?'-$':'$') + Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}); }
function fmtPct(v,d=2){ return (v>=0?'+':'') + v.toFixed(d) + '%'; }
function fmtPrice(p){ if(p<1) return '$'+p.toFixed(5); if(p<100) return '$'+p.toFixed(4); return '$'+p.toFixed(2); }
function fmtDur(seconds){
  if (seconds<60) return seconds+'s';
  if (seconds<3600) return Math.floor(seconds/60)+'m '+(seconds%60)+'s';
  const h=Math.floor(seconds/3600), m=Math.floor((seconds%3600)/60);
  return h+'h '+m+'m';
}

// ── Tactical Background controller (toggled by tweaks) ──────
function applyTweaks(t){
  const root = document.documentElement;
  // accent color
  const accents = {
    green: { c:'#00ffaa', bg:'rgba(0,255,170,.10)', bd:'rgba(0,255,170,.30)' },
    amber: { c:'#fbbf24', bg:'rgba(251,191,36,.10)', bd:'rgba(251,191,36,.35)' },
    blue:  { c:'#60a5fa', bg:'rgba(96,165,250,.10)', bd:'rgba(96,165,250,.30)' },
  };
  const a = accents[t.theme] || accents.green;
  root.style.setProperty('--accent', a.c);
  root.style.setProperty('--accent-bg', a.bg);
  root.style.setProperty('--accent-border', a.bd);

  // background intensity
  const bg = document.getElementById('tactical-bg');
  if (bg) bg.classList.toggle('off', !t.tacticalBg);

  // hud overlays
  document.body.classList.toggle('hud-overlays-off', !t.hudOverlays);

  // density
  document.body.classList.remove('density-sparse','density-balanced','density-dense');
  document.body.classList.add('density-' + (t.density || 'balanced'));
}

// ── Reticle SVG ────────────────────────────────────────────
function Reticle(){
  return (
    <div className="reticle">
      <svg viewBox="-100 -100 200 200" fill="none">
        <g className="ring-rotate">
          <circle r="80" stroke="currentColor" strokeOpacity=".35" strokeWidth=".4" strokeDasharray="2 4"/>
          <line x1="-90" y1="0" x2="-72" y2="0" stroke="currentColor" strokeOpacity=".5" strokeWidth=".6"/>
          <line x1="72"  y1="0" x2="90"  y2="0" stroke="currentColor" strokeOpacity=".5" strokeWidth=".6"/>
        </g>
        <g className="ring-rotate-rev">
          <circle r="55" stroke="currentColor" strokeOpacity=".5" strokeWidth=".5"/>
          <line y1="-65" x1="0" y2="-48" x2="0" stroke="currentColor" strokeOpacity=".6" strokeWidth=".8"/>
          <line y1="48"  x1="0" y2="65"  x2="0" stroke="currentColor" strokeOpacity=".6" strokeWidth=".8"/>
        </g>
        <circle r="3" fill="currentColor"/>
        <circle r="22" stroke="currentColor" strokeOpacity=".4" strokeWidth=".5"/>
      </svg>
    </div>
  );
}

// ── Equity Sparkline ────────────────────────────────────────
function EquitySparkline({ trades, initial }){
  const pts = useMemo(()=>{
    let eq = initial;
    const arr = [{x:0, y:eq}];
    [...trades].reverse().forEach((t,i)=>{ eq += t.pnl; arr.push({x:i+1, y:eq}); });
    return arr;
  }, [trades, initial]);
  if (pts.length<2) return <div style={{height:80, display:'flex',alignItems:'center',justifyContent:'center',color:'var(--fg-4)',fontFamily:'JetBrains Mono,monospace',fontSize:10,letterSpacing:'.18em',textTransform:'uppercase'}}>Awaiting trades…</div>;
  const minY = Math.min(...pts.map(p=>p.y)), maxY=Math.max(...pts.map(p=>p.y));
  const rangeY = maxY-minY || 1;
  const W=600, H=80, pad=4;
  const path = pts.map((p,i)=>{
    const x = pad + (p.x/(pts.length-1))*(W-2*pad);
    const y = H - pad - ((p.y-minY)/rangeY)*(H-2*pad);
    return (i?'L':'M')+' '+x.toFixed(1)+' '+y.toFixed(1);
  }).join(' ');
  const last = pts[pts.length-1];
  const isUp = last.y >= initial;
  const stroke = isUp ? 'var(--green)' : 'var(--red-2)';
  const lastX = pad + 1*(W-2*pad);
  const lastY = H - pad - ((last.y-minY)/rangeY)*(H-2*pad);
  const area = path + ` L ${lastX.toFixed(1)} ${H} L ${pad} ${H} Z`;
  return (
    <svg className="eq-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="eqg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor={stroke} stopOpacity=".25"/>
          <stop offset="100%" stopColor={stroke} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill="url(#eqg)"/>
      <path d={path} stroke={stroke} strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={lastX} cy={lastY} r="3" fill={stroke}/>
    </svg>
  );
}

// ── Position Card ───────────────────────────────────────────
function PositionCard({ pos, onOpen }){
  const isLong = pos.direction==='LONG';
  const profit = pos.unrealized_pnl >= 0;

  // flash on price tick
  const prev = useRef(pos.current_price);
  const [flash, setFlash] = useState('');
  useEffect(()=>{
    if (pos.current_price > prev.current) { setFlash('flash-green'); }
    else if (pos.current_price < prev.current) { setFlash('flash-red'); }
    prev.current = pos.current_price;
    const t=setTimeout(()=>setFlash(''),900);
    return ()=>clearTimeout(t);
  }, [pos.current_price]);

  const initialRisk = Math.abs(pos.entry_price - pos.initial_stop_loss);
  const moved = isLong ? (pos.current_price - pos.entry_price) : (pos.entry_price - pos.current_price);
  const rMult = initialRisk>0 ? moved/initialRisk : 0;

  // progress between SL and TP1
  let progress = 50;
  const { stop_loss:sl, entry_price:e, tp1, current_price:c } = pos;
  if (isLong){
    if (c>=e && tp1!=null){ const r=tp1-e; progress = r>0 ? 50+((c-e)/r)*50 : 50; }
    else if (c<e){ const r=e-sl; progress = r>0 ? ((c-sl)/r)*50 : 50; }
  } else {
    if (c<=e && tp1!=null){ const r=e-tp1; progress = r>0 ? 50+((e-c)/r)*50 : 50; }
    else if (c>e){ const r=sl-e; progress = r>0 ? ((sl-c)/r)*50 : 50; }
  }
  progress = Math.max(2, Math.min(98, progress));

  const timeOpen = fmtDur(Math.floor((Date.now()-pos.opened_at)/1000));

  return (
    <div className={`pos brackets ${flash}`} onClick={()=>onOpen(pos)}>
      <div className="corner-tag tl">// {pos.id.toUpperCase()}</div>
      <div className="corner-tag tr">{pos.confluence.toFixed(1)} CONF</div>

      {/* Top row */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:14,marginTop:6,flexWrap:'wrap'}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span className={`chip ${isLong?'chip-green':'chip-red'}`}>{isLong?'▲':'▼'} {pos.direction}</span>
          <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:18,letterSpacing:'.06em',color:'var(--fg)'}}>{pos.symbol}</span>
          <span className={`chip ${pos.trade_type==='scalp'?'chip-amber':pos.trade_type==='swing'?'chip-purple':'chip-blue'}`} style={{fontSize:9}}>{pos.trade_type}</span>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span className={`chip ${rMult>=0?'chip-green':'chip-red'}`}>{rMult>=0?'+':''}{rMult.toFixed(2)}R</span>
          <span className="mono" style={{fontWeight:800,fontSize:15,color:profit?'var(--green-soft)':'var(--red-2)'}}>{fmtPct(pos.unrealized_pnl_pct)}</span>
        </div>
      </div>

      {/* Metric row */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(4, 1fr)',gap:'10px 14px',marginBottom:14}}>
        <Mini label="Size"   value={fmtMoney(pos.quantity*pos.entry_price)} accent />
        <Mini label="Entry"  value={fmtPrice(pos.entry_price)} />
        <Mini label="Now"    value={fmtPrice(pos.current_price)} bold />
        <Mini label="P&L"    value={(profit?'+':'')+fmtMoney(pos.unrealized_pnl)} valueColor={profit?'var(--green-soft)':'var(--red-2)'} />
        <Mini label="Target" value={fmtMoney(pos.target_pnl)} valueColor="var(--green-soft)" />
        <Mini label="Risk"   value={fmtMoney(pos.risk_pnl)} valueColor="var(--red-2)" />
        <Mini label="Open"   value={timeOpen} valueColor="var(--amber)" />
        <Mini label="Lev"    value={pos.leverage+'×'} bold />
      </div>

      {/* Hud progress */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',marginBottom:6}}>
        <span className="mono" style={{fontSize:9,color:'var(--red-2)',textTransform:'uppercase',letterSpacing:'.16em',opacity:.85}}>SL · {fmtMoney(pos.risk_pnl)}</span>
        <span className="mono" style={{fontSize:9,textAlign:'center',color:'var(--fg-4)',textTransform:'uppercase',letterSpacing:'.16em'}}>ENTRY</span>
        <span className="mono" style={{fontSize:9,textAlign:'right',color:'var(--green-soft)',textTransform:'uppercase',letterSpacing:'.16em',opacity:.85}}>TP · {fmtMoney(pos.target_pnl)}</span>
      </div>
      <div className="hud-prog">
        <div className="tick" style={{left:'25%'}}/>
        <div className="tick" style={{left:'50%'}}/>
        <div className="tick" style={{left:'75%'}}/>
        <div className="marker" style={{left: progress + '%'}}/>
      </div>

      {/* Targets ladder */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginTop:14,gap:10}}>
        <div style={{display:'flex',alignItems:'center',gap:8,minWidth:0}}>
          <span className="mono" style={{fontSize:9,color:'var(--fg-4)',textTransform:'uppercase',letterSpacing:'.18em'}}>TARGETS {pos.targets_hit}/{pos.targets_hit+pos.targets_remaining}</span>
          <div style={{display:'flex',gap:4}}>
            {Array.from({length: pos.targets_hit + pos.targets_remaining}).map((_,i)=>(
              <div key={i} style={{
                width:18,height:5,borderRadius:2,
                background: i<pos.targets_hit ? (isLong?'var(--green)':'var(--red-2)') : 'rgba(255,255,255,.06)',
                border: i<pos.targets_hit ? 'none' : '1px solid var(--border-soft)',
                boxShadow: i<pos.targets_hit ? '0 0 8px '+(isLong?'rgba(0,255,170,.4)':'rgba(248,113,113,.4)') : 'none'
              }}/>
            ))}
          </div>
        </div>
        <div style={{display:'flex',gap:6,flexShrink:0}}>
          {pos.breakeven_active && <span className="chip chip-blue">BE</span>}
          {pos.trailing_active && <span className="chip chip-accent">TRAIL</span>}
          <span className="chip">CHART →</span>
        </div>
      </div>
    </div>
  );
}

function Mini({ label, value, accent, bold, valueColor }){
  return (
    <div>
      <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:4}}>{label}</div>
      <div className="mono" style={{fontSize:13,fontWeight: bold?800:600, color: valueColor || (accent?'var(--accent)':'var(--fg)')}}>{value}</div>
    </div>
  );
}

// ── Position Chart Modal ────────────────────────────────────
function PositionChartModal({ pos, onClose }){
  if (!pos) return null;
  const isLong = pos.direction === 'LONG';
  const levels = [
    { label:'TP3',     price: pos.tp_final, color:'#86efac' },
    { label:'TP2',     price: pos.tp2,      color:'#4ade80' },
    { label:'TP1',     price: pos.tp1,      color:'#22c55e' },
    { label:'CURRENT', price: pos.current_price, color:'#fbbf24' },
    { label:'ENTRY',   price: pos.entry_price,   color:'#60a5fa' },
    { label:'STOP',    price: pos.stop_loss, color:'#f87171' },
  ].sort((a,b)=>b.price-a.price);
  const prices = levels.map(l=>l.price);
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  const range = maxP-minP || maxP*.01;

  // synthetic candles biased by direction
  const candles = useMemo(()=>{
    const N = 36;
    const arr = [];
    let p = pos.entry_price * (isLong ? 0.985 : 1.015);
    for (let i=0;i<N;i++){
      const drift = isLong ? 0.0015 : -0.0015;
      const vol = (Math.sin(i*1.7)+Math.cos(i*0.9))*0.004 + (Math.random()-.5)*0.005;
      const open = p;
      const close = p * (1 + drift + vol);
      const high = Math.max(open,close) * (1 + Math.abs(Math.random()*0.003));
      const low  = Math.min(open,close) * (1 - Math.abs(Math.random()*0.003));
      arr.push({open,close,high,low});
      p = close;
    }
    // anchor end at current
    const factor = pos.current_price / arr[arr.length-1].close;
    arr.forEach(c=>{ c.open*=factor; c.close*=factor; c.high*=factor; c.low*=factor; });
    return arr;
  }, [pos]);

  const allP = [...prices, ...candles.flatMap(c=>[c.high,c.low])];
  const yMin = Math.min(...allP)*.998;
  const yMax = Math.max(...allP)*1.002;
  const yRng = yMax - yMin;
  const W = 540, H = 280, leftPad=10, rightPad=70, topPad=14, botPad=14;
  const innerW = W-leftPad-rightPad;
  const innerH = H-topPad-botPad;
  const cw = innerW / candles.length;

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" style={{maxWidth:620}} onClick={e=>e.stopPropagation()}>
        <div style={{padding:'14px 18px',borderBottom:'1px solid var(--border-soft)',background:'rgba(0,0,0,.35)',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <span className={`chip ${isLong?'chip-green':'chip-red'}`}>{isLong?'▲':'▼'} {pos.direction}</span>
            <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:18,letterSpacing:'.08em'}}>{pos.symbol}</span>
            <span className="chip">{pos.trade_type}</span>
          </div>
          <button className="btn" style={{padding:'6px 10px'}} onClick={onClose}>✕ CLOSE</button>
        </div>
        <div style={{padding:'14px 18px'}}>
          <svg viewBox={`0 0 ${W} ${H}`} style={{width:'100%',height:'auto',background:'rgba(0,0,0,.35)',border:'1px solid var(--border-soft)',borderRadius:8}}>
            {/* grid */}
            {[0,.25,.5,.75,1].map(g=>(
              <line key={g} x1={leftPad} x2={W-rightPad} y1={topPad+g*innerH} y2={topPad+g*innerH} stroke="rgba(255,255,255,.05)" strokeDasharray="2 3"/>
            ))}
            {/* candles */}
            {candles.map((c,i)=>{
              const x = leftPad + i*cw + cw*0.15;
              const cx = leftPad + i*cw + cw/2;
              const yO = topPad + ((yMax-c.open)/yRng)*innerH;
              const yC = topPad + ((yMax-c.close)/yRng)*innerH;
              const yH = topPad + ((yMax-c.high)/yRng)*innerH;
              const yL = topPad + ((yMax-c.low)/yRng)*innerH;
              const up = c.close>=c.open;
              const fill = up ? '#22c55e' : '#f87171';
              const w = cw*0.7;
              return (
                <g key={i} opacity={i<candles.length-1?.85:1}>
                  <line x1={cx} x2={cx} y1={yH} y2={yL} stroke={fill} strokeWidth=".8" opacity=".7"/>
                  <rect x={x} width={w} y={Math.min(yO,yC)} height={Math.max(1.2,Math.abs(yC-yO))} fill={fill} opacity={up?.85:.85} stroke={fill} strokeOpacity=".4"/>
                </g>
              );
            })}
            {/* level lines */}
            {levels.map((l,i)=>{
              const y = topPad + ((yMax-l.price)/yRng)*innerH;
              if (y<topPad-2 || y>H-botPad+2) return null;
              return (
                <g key={i}>
                  <line x1={leftPad} x2={W-rightPad} y1={y} y2={y} stroke={l.color} strokeWidth=".7" strokeDasharray="3 3" opacity=".7"/>
                  <rect x={W-rightPad+2} y={y-9} width={66} height={18} fill={l.color} opacity=".15" stroke={l.color} strokeOpacity=".55"/>
                  <text x={W-rightPad+6} y={y+4} fill={l.color} fontFamily="JetBrains Mono,monospace" fontSize="9" fontWeight="700" letterSpacing=".15em">{l.label}</text>
                  <text x={W-2} y={y+4} fill={l.color} fontFamily="JetBrains Mono,monospace" fontSize="9" fontWeight="700" textAnchor="end">{l.price<1?l.price.toFixed(5):l.price<100?l.price.toFixed(3):l.price.toFixed(2)}</text>
                </g>
              );
            })}
            {/* current price marker */}
            {(() => {
              const y = topPad + ((yMax-pos.current_price)/yRng)*innerH;
              return <circle cx={W-rightPad-4} cy={y} r="4" fill="#fbbf24" style={{filter:'drop-shadow(0 0 6px #fbbf24)'}}/>;
            })()}
          </svg>

          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8,marginTop:14}}>
            {levels.map((l,i)=>(
              <div key={i} style={{padding:'8px 10px',border:'1px solid var(--border-soft)',borderRadius:8,background:'rgba(0,0,0,.3)'}}>
                <div className="mono" style={{fontSize:9,color:l.color,letterSpacing:'.18em',textTransform:'uppercase',marginBottom:4,fontWeight:700}}>{l.label}</div>
                <div className="mono" style={{fontSize:13,fontWeight:800,color:l.color}}>{l.price<1?'$'+l.price.toFixed(5):l.price<100?'$'+l.price.toFixed(3):'$'+l.price.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Trade History Item ──────────────────────────────────────
function HistoryItem({ trade }){
  const [expanded, setExpanded] = useState(false);
  const isLong = trade.direction === 'LONG';
  const profit = trade.pnl >= 0;
  const dur = fmtDur(Math.floor((trade.exit_time - trade.entry_time)/1000));
  const reason = (trade.exit_reason||'unknown').replace(/_/g,' ');
  return (
    <div className={`hist ${expanded?'expanded':''}`} onClick={()=>setExpanded(!expanded)}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10}}>
        <div style={{display:'flex',alignItems:'center',gap:12,minWidth:0}}>
          <span className={`chip ${isLong?'chip-green':'chip-red'}`}>{trade.direction}</span>
          <div style={{minWidth:0}}>
            <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
              <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:14,letterSpacing:'.06em'}}>{trade.symbol}</span>
              <span className="chip" style={{fontSize:9}}>{reason}</span>
              <span className={`chip ${trade.trade_type==='scalp'?'chip-amber':trade.trade_type==='swing'?'chip-purple':'chip-blue'}`} style={{fontSize:9}}>{trade.trade_type}</span>
            </div>
            <div className="mono" style={{fontSize:11,color:'var(--fg-3)',marginTop:3}}>
              {fmtPrice(trade.entry_price)} <span style={{color:profit?'var(--green-soft)':'var(--red-2)'}}>{isLong?'→':'→'}</span> {fmtPrice(trade.exit_price)} · {dur}
            </div>
          </div>
        </div>
        <div style={{textAlign:'right'}}>
          <div className="mono" style={{fontSize:13,fontWeight:800,color:profit?'var(--green-soft)':'var(--red-2)'}}>{(profit?'+':'')+fmtMoney(trade.pnl)}</div>
          <div className="mono" style={{fontSize:10,color:profit?'var(--green-soft)':'var(--red-2)',opacity:.75}}>{fmtPct(trade.pnl_pct)}</div>
        </div>
      </div>
      {expanded && (
        <div style={{marginTop:12,paddingTop:12,borderTop:'1px solid var(--border-soft)',display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:14}}>
          <Stack label="Timing">
            <Row k="In"  v={new Date(trade.entry_time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}/>
            <Row k="Out" v={new Date(trade.exit_time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}/>
            <Row k="Dur" v={dur} accent/>
          </Stack>
          <Stack label="Excursion">
            <Row k="MFE" v={fmtPct(trade.max_favorable)} green/>
            <Row k="MAE" v={fmtPct(-Math.abs(trade.max_adverse))} red/>
            <Row k="Qty" v={trade.quantity.toString()}/>
          </Stack>
          <Stack label="Execution">
            <Row k="TPs Hit" v={trade.targets_hit.length+' / '+(trade.targets_hit.length+(trade.exit_reason==='stop_loss'?2:0))} amber/>
            <Row k="Conf"    v={trade.confidence_score.toString()}/>
            <Row k="R Mult"  v={(trade.pnl_pct/1.5).toFixed(2)+'R'}/>
          </Stack>
        </div>
      )}
    </div>
  );
}
function Stack({ label, children }){
  return (
    <div>
      <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:6}}>{label}</div>
      <div style={{display:'flex',flexDirection:'column',gap:4}}>{children}</div>
    </div>
  );
}
function Row({ k, v, accent, green, red, amber }){
  let color = 'var(--fg-2)';
  if (accent) color = 'var(--accent)';
  if (green) color = 'var(--green-soft)';
  if (red) color = 'var(--red-2)';
  if (amber) color = 'var(--amber)';
  return (
    <div style={{display:'flex',justifyContent:'space-between',fontFamily:'JetBrains Mono,monospace',fontSize:11}}>
      <span style={{color:'var(--fg-4)'}}>{k}</span>
      <span style={{color,fontWeight:600}}>{v}</span>
    </div>
  );
}

// ── Watchlist Radar (mini) ──────────────────────────────────
function WatchlistRadar({ items }){
  return (
    <div className="radar-wrap">
      <svg viewBox="-100 -100 200 200" style={{width:'100%',height:'100%'}}>
        <defs>
          <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0"/>
            <stop offset="100%" stopColor="var(--accent)" stopOpacity=".5"/>
          </linearGradient>
        </defs>
        {/* rings */}
        {[30,55,80].map(r=><circle key={r} r={r} fill="none" stroke="var(--accent)" strokeOpacity=".18" strokeWidth=".4"/>)}
        <line x1="-90" y1="0" x2="90" y2="0" stroke="var(--accent)" strokeOpacity=".15" strokeWidth=".4"/>
        <line x1="0" y1="-90" x2="0" y2="90" stroke="var(--accent)" strokeOpacity=".15" strokeWidth=".4"/>
        {/* sweep */}
        <g className="radar-sweep">
          <path d="M 0 0 L 88 0 A 88 88 0 0 0 67 -57 Z" fill="url(#sweep)"/>
          <line x1="0" y1="0" x2="88" y2="0" stroke="var(--accent)" strokeOpacity=".55" strokeWidth=".6"/>
        </g>
        {/* blips */}
        {items.slice(0,7).map((it,i)=>{
          const angle = (i/7)*Math.PI*2 - Math.PI/2;
          const dist = 28 + (10-it.score)*5;
          const x = Math.cos(angle)*dist;
          const y = Math.sin(angle)*dist;
          const armed = it.status==='ARMED';
          return (
            <g key={it.symbol}>
              <circle cx={x} cy={y} r={armed?2.6:1.6} fill={armed?'var(--accent)':'var(--fg-3)'}>
                {armed && <animate attributeName="opacity" values="1;.3;1" dur="2s" repeatCount="indefinite"/>}
              </circle>
              {armed && <circle cx={x} cy={y} r="6" fill="none" stroke="var(--accent)" strokeOpacity=".3"><animate attributeName="r" values="3;9" dur="2s" repeatCount="indefinite"/><animate attributeName="opacity" values=".7;0" dur="2s" repeatCount="indefinite"/></circle>}
              <text x={x+5} y={y-3} fontFamily="JetBrains Mono, monospace" fontSize="6" fill={armed?'var(--accent)':'var(--fg-3)'} fontWeight="700">{it.symbol.split('/')[0]}</text>
            </g>
          );
        })}
        {/* center */}
        <circle r="3" fill="var(--accent)"/>
      </svg>
    </div>
  );
}

// ── App ─────────────────────────────────────────────────────
function StatusApp(){
  const [t, setTweak] = window.useTweaks({
    theme: 'green',
    density: 'balanced',
    tacticalBg: true,
    hudOverlays: true,
    layout: 'split',
    simSpeed: 1,
    tradingMode: 'live',
  });
  useEffect(()=>{ applyTweaks(t); }, [t]);

  const [running, setRunning] = useState(true);
  const [showKill, setShowKill] = useState(false);
  const [killing, setKilling] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [openPos, setOpenPos] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [uptime, setUptime] = useState(60*60*3 + 60*42);  // 3h 42m
  const [nextScan, setNextScan] = useState(47);
  const [positions, setPositions] = useState(SEED_POSITIONS);
  const [trades, setTrades] = useState(SEED_HISTORY);
  const [scanProgress, setScanProgress] = useState({ done: 18, total: 25, passed: 3, rejected: 15, current: 'INJ/USDT', recent: [
    { sym:'BTC', passed:true }, { sym:'ETH', passed:true }, { sym:'SOL', passed:true },
    { sym:'TIA', passed:false }, { sym:'AAVE', passed:false }, { sym:'OP', passed:false },
    { sym:'NEAR', passed:false }, { sym:'INJ', passed:false }, { sym:'ARB', passed:false },
  ]});
  const [logs, setLogs] = useState([
    { t:'14:42:18', sym:'BTC/USDT',  passed:true,  reason:'OB+FVG aligned · BOS confirmed', conf:8.2 },
    { t:'14:41:55', sym:'ETH/USDT',  passed:true,  reason:'4H OB · sweep + displacement',   conf:7.4 },
    { t:'14:41:32', sym:'SOL/USDT',  passed:true,  reason:'liquidity sweep · CHoCH 15m',    conf:7.8 },
    { t:'14:41:09', sym:'AVAX/USDT', passed:false, reason:'HTF misaligned · regime CHOP',   conf:5.1 },
    { t:'14:40:46', sym:'TIA/USDT',  passed:false, reason:'displacement < 1.5 ATR',         conf:4.6 },
    { t:'14:40:23', sym:'AAVE/USDT', passed:false, reason:'no fresh OB in last 50 candles', conf:3.9 },
    { t:'14:40:00', sym:'LINK/USDT', passed:false, reason:'volume gate failed',             conf:3.2 },
    { t:'14:39:37', sym:'OP/USDT',   passed:false, reason:'BTC impulse veto',               conf:0   },
  ]);

  // tick clock + uptime
  useEffect(()=>{
    const id = setInterval(()=>{ setNow(Date.now()); setUptime(u=>u+1); setNextScan(s=> s>0?s-1:Math.floor(Math.random()*45+30)); }, 1000 / (t.simSpeed || 1));
    return ()=>clearInterval(id);
  }, [t.simSpeed]);

  // simulated price ticks
  useEffect(()=>{
    const id = setInterval(()=>{
      setPositions(prev => prev.map(p=>{
        const drift = (Math.random()-0.48) * p.entry_price * 0.0008;
        const price = p.current_price + drift;
        const isLong = p.direction === 'LONG';
        const pnl = (isLong ? price - p.entry_price : p.entry_price - price) * p.quantity;
        const pnlPct = (pnl / (p.entry_price * p.quantity)) * 100 * p.leverage;
        return {...p, current_price: price, unrealized_pnl: pnl, unrealized_pnl_pct: pnlPct };
      }));
    }, 1500 / (t.simSpeed || 1));
    return ()=>clearInterval(id);
  }, [t.simSpeed]);

  // simulated scan progress
  useEffect(()=>{
    if (!running) return;
    const id = setInterval(()=>{
      setScanProgress(sp=>{
        if (sp.done >= sp.total) {
          // restart cycle
          return { done: 1, total: 25, passed: Math.random()<.5?1:0, rejected: Math.random()<.5?0:1, current: SCAN_SYMBOLS[0]+'/USDT', recent: [{sym: SCAN_SYMBOLS[0], passed: Math.random()<.4}] };
        }
        const passed = Math.random()<.2;
        const sym = SCAN_SYMBOLS[(sp.done) % SCAN_SYMBOLS.length];
        return {
          done: sp.done+1,
          total: sp.total,
          passed: sp.passed + (passed?1:0),
          rejected: sp.rejected + (passed?0:1),
          current: SCAN_SYMBOLS[(sp.done+1) % SCAN_SYMBOLS.length] + '/USDT',
          recent: [{ sym, passed }, ...sp.recent].slice(0,12),
        };
      });
      setLogs(prev=>{
        const sym = SCAN_SYMBOLS[Math.floor(Math.random()*SCAN_SYMBOLS.length)];
        const passed = Math.random()<.2;
        const conf = passed ? +(7+Math.random()*1.5).toFixed(1) : +(2+Math.random()*4).toFixed(1);
        const reasons = passed
          ? ['OB+FVG aligned · BOS confirmed','4H OB · sweep + displacement','liquidity sweep · CHoCH 15m','HTF + LTF aligned · trail tight']
          : ['HTF misaligned · regime CHOP','displacement < 1.5 ATR','no fresh OB','volume gate failed','BTC impulse veto','spread > limit'];
        const time = new Date(Date.now());
        const t = `${String(time.getHours()).padStart(2,'0')}:${String(time.getMinutes()).padStart(2,'0')}:${String(time.getSeconds()).padStart(2,'0')}`;
        return [{ t, sym: sym+'/USDT', passed, reason: reasons[Math.floor(Math.random()*reasons.length)], conf }, ...prev].slice(0,12);
      });
    }, 2200 / (t.simSpeed || 1));
    return ()=>clearInterval(id);
  }, [running, t.simSpeed]);

  const handleStop = () => {
    setStopping(true);
    setTimeout(()=>{ setRunning(false); setStopping(false); }, 900);
  };
  const handleKill = () => {
    setKilling(true); setShowKill(false);
    setTimeout(()=>{ setRunning(false); setPositions([]); setKilling(false); }, 1100);
  };
  const handleStart = () => setRunning(true);

  // stats
  const winCount = trades.filter(t=>t.pnl>0).length;
  const winRate = (winCount/trades.length)*100;
  const totalPnl = trades.reduce((a,t)=>a+t.pnl,0) + positions.reduce((a,p)=>a+p.unrealized_pnl,0);
  const initialBal = 5000;
  const balance = initialBal + trades.reduce((a,t)=>a+t.pnl,0);
  const equity = balance + positions.reduce((a,p)=>a+p.unrealized_pnl,0);

  const isLive = t.tradingMode === 'live';
  const isLayoutSingle = t.layout === 'single';

  return (
    <div className="shell">
      {/* Topbar */}
      <div className="topbar" style={{display: window.__BOT_SHELL__ ? 'none' : ''}}>
        <div className="brand">
          <div className="brand-mark">
            <svg width="20" height="20" viewBox="-12 -12 24 24" fill="none">
              <circle r="9" stroke="currentColor" strokeWidth="1.2" style={{color:'var(--accent)'}}/>
              <line x1="-11" y1="0" x2="-5" y2="0" stroke="currentColor" strokeWidth="1.2" style={{color:'var(--accent)'}}/>
              <line x1="11" y1="0" x2="5" y2="0" stroke="currentColor" strokeWidth="1.2" style={{color:'var(--accent)'}}/>
              <line x1="0" y1="-11" x2="0" y2="-5" stroke="currentColor" strokeWidth="1.2" style={{color:'var(--accent)'}}/>
              <line x1="0" y1="11" x2="0" y2="5" stroke="currentColor" strokeWidth="1.2" style={{color:'var(--accent)'}}/>
              <circle r="2" fill="currentColor" style={{color:'var(--accent)'}}/>
            </svg>
          </div>
          <div>
            <div className="brand-name">SniperSight<span style={{color:'var(--accent)'}}>·</span>HUD</div>
            <div className="brand-sub">v1.0 · institutional scanner</div>
          </div>
        </div>
        <nav className="nav">
          <a href="#">Intel</a>
          <a href="#">Scanner</a>
          <a href="#" className="active">Bot Status</a>
          <a href="#">Journal</a>
          <a href="#">Training</a>
        </nav>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <span className="chip chip-green">● ONLINE</span>
          <span className="chip">UTC {new Date(now).toUTCString().slice(17,25)}</span>
        </div>
      </div>

      {/* Page head */}
      <div className="page-head">
        <div className="page-title">
          <div className="icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <rect x="4" y="6" width="16" height="12" rx="2" stroke={isLive?'var(--red)':'var(--amber)'} strokeWidth="1.7"/>
              <circle cx="9"  cy="12" r="1.5" fill={isLive?'var(--red)':'var(--amber)'}/>
              <circle cx="15" cy="12" r="1.5" fill={isLive?'var(--red)':'var(--amber)'}/>
              <line x1="9"  y1="3" x2="9"  y2="6" stroke={isLive?'var(--red)':'var(--amber)'} strokeWidth="1.7"/>
              <line x1="15" y1="3" x2="15" y2="6" stroke={isLive?'var(--red)':'var(--amber)'} strokeWidth="1.7"/>
            </svg>
          </div>
          <div>
            <h1 className={isLive?'live':''}>Live Deployment</h1>
            <div className="sub">{isLive?'real money · phemex perpetuals':'testnet · simulated fills'}</div>
          </div>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
          <span className={`chip ${running?'chip-green':'chip-red'}`}>{running?'● RUNNING':'⏹ STOPPED'}</span>
          <span className={`chip ${isLive?'chip-red':'chip-amber'}`}>{isLive?'⚠ LIVE — REAL MONEY':'TESTNET'}</span>
          <span className="chip">SESSION 7F2A·9D</span>
        </div>
      </div>

      {/* COMMAND CENTER */}
      <section className="panel panel-accent" style={{marginBottom:18}}>
        <Reticle/>
        <div className="corner-tag tl">// CMD-CENTER</div>
        <div className="corner-tag tr">PHANTOM ENGINE</div>
        <div style={{padding:'22px 22px 18px'}}>
          {/* Identity row */}
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:14,flexWrap:'wrap',marginBottom:18}}>
            <div style={{display:'flex',alignItems:'center',gap:14}}>
              <div className={`orb ${running?'':isLive?'red':'amber'}`}>
                <div className="ping"/>
                <div className="blur"/>
                <div className="core"/>
              </div>
              <div>
                <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap',marginBottom:4}}>
                  <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:18,letterSpacing:'.15em',color:'var(--fg)',textTransform:'uppercase'}}>Phantom Engine</span>
                  <span className={`chip ${isLive?'chip-red':'chip-amber'}`}>{isLive?'LIVE — REAL':'TESTNET'}</span>
                  <span className={`chip ${running?'chip-green':'chip-red'}`}>{running?'LIVE':'PAUSED'}</span>
                </div>
                <div className="mono" style={{fontSize:11,color:'var(--fg-4)',letterSpacing:'.12em'}}>⏱ {fmtDur(uptime)} · session 7f2a9d · binance + phemex feed</div>
              </div>
            </div>
            <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
              {running ? (
                <>
                  <button className="btn btn-red" onClick={handleStop} disabled={stopping}>{stopping?'⟳ STOPPING…':'⏹ STOP'}</button>
                  <button className="btn btn-orange" onClick={()=>setShowKill(true)}>☠ KILL</button>
                </>
              ) : (
                <>
                  <button className="btn btn-green" onClick={handleStart}>▶ START</button>
                  <button className="btn btn-icon" title="Reset">⟳</button>
                </>
              )}
              <button className="btn btn-cyan">⌬ ANALYZE</button>
            </div>
          </div>

          {/* Kill confirm */}
          {showKill && (
            <div style={{padding:14,border:'1px solid rgba(248,113,113,.6)',borderRadius:10,background:'rgba(248,113,113,.10)',marginBottom:18}}>
              <div style={{display:'flex',alignItems:'center',gap:8,color:'var(--red-2)',fontFamily:'Share Tech Mono,monospace',fontSize:14,letterSpacing:'.18em',textTransform:'uppercase',marginBottom:6}}>☠ Confirm Kill Switch</div>
              <p style={{margin:'0 0 12px',fontSize:12,color:'var(--fg-2)',lineHeight:1.5}}>Cancel all open orders and close all <b>{positions.length}</b> positions at market price immediately.{isLive && ' This will execute with real funds.'}</p>
              <div style={{display:'flex',gap:8}}>
                <button className="btn" onClick={()=>setShowKill(false)}>Cancel</button>
                <button className="btn btn-red" onClick={handleKill} disabled={killing}>{killing?'⟳ EXECUTING…':'☠ Confirm Kill Switch'}</button>
              </div>
            </div>
          )}

          {/* Metrics grid */}
          <div style={{display:'grid',gridTemplateColumns:'repeat(4, minmax(0,1fr))',gap:10}} className="metrics-grid">
            <div className="metric-tile">
              <div className="metric-label">Running</div>
              <div className="metric-value">{fmtDur(uptime)}</div>
              <div className="metric-sub">session uptime</div>
            </div>
            <div className="metric-tile">
              <div className="metric-label">Regime</div>
              <div className="metric-value" style={{color:'var(--blue)'}}>BULL</div>
              <div className="metric-sub">bull · trend confirmed</div>
            </div>
            <div className="metric-tile">
              <div className="metric-label">Next Scan</div>
              <div className="metric-value hud-glow-amber">{fmtDur(nextScan)}</div>
              <div className="metric-sub">until next sweep</div>
            </div>
            <div className="metric-tile">
              <div className="metric-label">Min Score</div>
              <div className="metric-value">≥ 7.0</div>
              <div className="metric-sub">confluence</div>
            </div>
          </div>

          {/* Config pills */}
          <div style={{display:'flex',gap:6,flexWrap:'wrap',marginTop:14}}>
            <span className="chip">SNIPER MODE · BALANCED</span>
            <span className="chip">SENSITIVITY · STRICT</span>
            <span className="chip">DURATION · 8H</span>
            <span className="chip">MAX SLOTS · 5</span>
            <span className="chip">RISK · 1.5%</span>
            <span className="chip">LEVERAGE · 5×</span>
            <span className="chip">NOTIFY · TELEGRAM</span>
          </div>

          {/* Scan progress */}
          <div style={{marginTop:16,paddingTop:14,borderTop:'1px solid var(--border-soft)'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,marginBottom:8,flexWrap:'wrap'}}>
              <div className="mono" style={{fontSize:11,color:'var(--fg-4)',letterSpacing:'.16em',textTransform:'uppercase'}}>
                <span style={{color:'var(--amber)'}}>◉</span> {running? `SCANNING ${scanProgress.current}` : 'SCAN PAUSED'}<span className="cursor-blink">_</span>
              </div>
              <div style={{display:'flex',gap:14,fontFamily:'JetBrains Mono,monospace',fontSize:11}}>
                <span style={{color:'var(--green-soft)',fontWeight:700}}>{scanProgress.passed} passed</span>
                <span style={{color:'var(--fg-3)'}}>{scanProgress.rejected} filtered</span>
                <span style={{color:'var(--fg-4)'}}>{scanProgress.done}/{scanProgress.total}</span>
              </div>
            </div>
            <div style={{position:'relative',height:4,borderRadius:2,background:'rgba(0,0,0,.5)',overflow:'hidden'}}>
              <div style={{
                position:'absolute',inset:0,
                width: ((scanProgress.done/scanProgress.total)*100)+'%',
                background: running ? 'linear-gradient(90deg, rgba(251,191,36,.7), rgba(251,191,36,1))' : 'rgba(120,120,120,.4)',
                boxShadow: running ? '0 0 14px rgba(251,191,36,.5)':'none',
                transition:'width .8s ease',
              }}/>
              {running && <div style={{position:'absolute',inset:0,width:'30%',background:'linear-gradient(90deg,transparent,rgba(255,255,255,.18),transparent)',animation:'barShimmer 1.6s ease-in-out infinite'}}/>}
            </div>
            <div style={{display:'flex',gap:6,marginTop:10,overflowX:'auto'}} className="no-scrollbar">
              {scanProgress.recent.slice(0,12).map((r,i)=>(
                <span key={i} className={`chip ${r.passed?'chip-green':''}`} style={{flexShrink:0,fontSize:9}}>{r.passed?'✓ ':''}{r.sym}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* MAIN GRID */}
      <div className={`layout-grid ${isLayoutSingle?'single':''}`}>
        {/* LEFT COL */}
        <div className="col">

          {/* Equity / P&L panel */}
          <section className="panel">
            <div className="sec-head">
              <div className="sec-title"><span className="dot"/> Account · Equity Curve</div>
              <div style={{display:'flex',gap:8}}>
                <span className="chip">USD · {trades.length} TRADES</span>
                <span className={`chip ${totalPnl>=0?'chip-green':'chip-red'}`}>{totalPnl>=0?'+':''}{fmtMoney(totalPnl)}</span>
              </div>
            </div>
            <div style={{padding:'18px 22px'}}>
              <div style={{display:'grid',gridTemplateColumns:'repeat(4, minmax(0,1fr))',gap:10,marginBottom:14}}>
                <div className="metric-tile">
                  <div className="metric-label">Equity</div>
                  <div className="metric-value">{fmtMoney(equity)}</div>
                  <div className="metric-sub" style={{color: equity>=initialBal?'var(--green-soft)':'var(--red-2)'}}>{fmtPct(((equity-initialBal)/initialBal)*100)}</div>
                </div>
                <div className="metric-tile">
                  <div className="metric-label">Realized</div>
                  <div className="metric-value" style={{color:'var(--green-soft)'}}>+{fmtMoney(trades.reduce((a,t)=>a+t.pnl,0))}</div>
                  <div className="metric-sub">closed pnl</div>
                </div>
                <div className="metric-tile">
                  <div className="metric-label">Unrealized</div>
                  <div className="metric-value" style={{color: positions.reduce((a,p)=>a+p.unrealized_pnl,0)>=0?'var(--green-soft)':'var(--red-2)'}}>{positions.reduce((a,p)=>a+p.unrealized_pnl,0)>=0?'+':''}{fmtMoney(positions.reduce((a,p)=>a+p.unrealized_pnl,0))}</div>
                  <div className="metric-sub">{positions.length} open</div>
                </div>
                <div className="metric-tile">
                  <div className="metric-label">Win Rate</div>
                  <div className="metric-value hud-glow">{winRate.toFixed(0)}%</div>
                  <div className="metric-sub">{winCount} of {trades.length}</div>
                </div>
              </div>
              <EquitySparkline trades={trades} initial={initialBal}/>
              <div style={{display:'flex',justifyContent:'space-between',marginTop:6}}>
                <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>session start ${initialBal.toFixed(2)}</span>
                <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>now {fmtMoney(equity)}</span>
              </div>
            </div>
          </section>

          {/* Open Positions */}
          <section className="panel">
            <div className="sec-head">
              <div className="sec-title"><span className="dot"/> Open Positions</div>
              <span className="chip">{positions.length} ACTIVE · MAX 5</span>
            </div>
            <div style={{padding:'14px 18px',display:'flex',flexDirection:'column',gap:10}}>
              {positions.length === 0 && (
                <div style={{textAlign:'center',padding:'40px 0',color:'var(--fg-4)',fontFamily:'JetBrains Mono,monospace',fontSize:12,letterSpacing:'.18em',textTransform:'uppercase'}}>// no open positions · awaiting signal</div>
              )}
              {positions.map(p => <PositionCard key={p.id} pos={p} onOpen={setOpenPos}/>)}
            </div>
          </section>

          {/* Trade History */}
          <section className="panel">
            <div className="sec-head">
              <div className="sec-title"><span className="dot"/> Trade Log · Session</div>
              <span className="chip">{trades.length} CLOSED</span>
            </div>
            <div style={{padding:'14px 18px',display:'flex',flexDirection:'column',gap:8}}>
              {trades.map(tr => <HistoryItem key={tr.id} trade={tr}/>)}
            </div>
          </section>
        </div>

        {/* RIGHT COL */}
        <div className="col">
          {/* Watchlist Radar */}
          <section className="panel">
            <Reticle/>
            <div className="sec-head">
              <div className="sec-title"><span className="dot"/> Watchlist Radar</div>
              <span className="chip chip-accent">{SEED_WATCHLIST.filter(w=>w.status==='ARMED').length} ARMED</span>
            </div>
            <div style={{padding:'14px 18px'}}>
              <WatchlistRadar items={SEED_WATCHLIST}/>
              <div style={{marginTop:10}}>
                {SEED_WATCHLIST.map(w => (
                  <div className="watch-row" key={w.symbol}>
                    <div style={{display:'flex',alignItems:'center',gap:8,minWidth:0}}>
                      <span className={`chip ${w.status==='ARMED'?'chip-accent':w.status==='WATCH'?'chip-amber':''}`} style={{fontSize:9}}>{w.status}</span>
                      <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:13,letterSpacing:'.06em'}}>{w.symbol.split('/')[0]}</span>
                    </div>
                    <div style={{display:'flex',alignItems:'center',gap:10}}>
                      <span className="mono" style={{fontSize:10,color:'var(--fg-4)'}}>{w.regime}</span>
                      <span className="mono" style={{fontSize:11,fontWeight:700,color:w.score>=7?'var(--green-soft)':w.score>=6?'var(--amber)':'var(--fg-4)'}}>{w.score.toFixed(1)}</span>
                      <span className="mono" style={{fontSize:11,color:w.change>=0?'var(--green-soft)':'var(--red-2)',width:48,textAlign:'right'}}>{fmtPct(w.change,1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Live scan log */}
          <section className="panel">
            <div className="sec-head">
              <div className="sec-title"><span className="dot"/> Scanner Console</div>
              <span className="chip chip-amber">// LIVE</span>
            </div>
            <div style={{padding:'14px 18px',background:'rgba(0,0,0,.45)',maxHeight:380,overflowY:'auto',borderTop:'1px solid var(--border-soft)'}}>
              <div className="term" style={{fontSize:14,color:'var(--green)',marginBottom:8,opacity:.7}}>
                {`> tail -f /var/log/snipersight/scanner.log`}<span className="cursor-blink">_</span>
              </div>
              {logs.map((l,i)=>(
                <div className="log-row" key={i}>
                  <span className="t">{l.t}</span>
                  <span className={l.passed?'pass':'rej'}>{l.passed?'PASS':'FILT'}</span>
                  <span><span className="sym">{l.sym}</span> · <span style={{color:l.passed?'var(--green-soft)':'var(--fg-3)'}}>{l.reason}</span></span>
                  <span className="mono" style={{fontSize:11,color:l.passed?'var(--green-soft)':'var(--fg-4)'}}>{l.conf.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Risk panel */}
          <section className="panel">
            <div className="sec-head">
              <div className="sec-title"><span className="dot"/> Risk · Exposure</div>
              <span className="chip chip-green">WITHIN LIMITS</span>
            </div>
            <div style={{padding:'14px 18px',display:'flex',flexDirection:'column',gap:14}}>
              <RiskBar label="Capital at Risk" value={positions.length>0?2.4:0} max={5} unit="%" />
              <RiskBar label="Slot Usage" value={positions.length} max={5} unit="" />
              <RiskBar label="Daily Loss" value={1.2} max={3} unit="%" amber />
              <RiskBar label="Correlation" value={0.42} max={1} unit="" amber />
              <div style={{display:'flex',justifyContent:'space-between',padding:'10px 0 0',borderTop:'1px solid var(--border-soft)'}}>
                <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>kill switch</span>
                <span className="chip chip-green">● ARMED</span>
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* footer status strip */}
      <div style={{marginTop:24,padding:'12px 18px',border:'1px solid var(--border-soft)',borderRadius:10,background:'rgba(0,0,0,.3)',display:'flex',alignItems:'center',justifyContent:'space-between',gap:14,flexWrap:'wrap'}}>
        <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
          <span className="chip chip-green">● BINANCE WS</span>
          <span className="chip chip-green">● PHEMEX REST</span>
          <span className="chip chip-green">● TELEGRAM</span>
          <span className="chip">● BACKEND 41ms</span>
        </div>
        <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>build 1.0.0+5cdb504 · {new Date(now).toISOString().slice(0,19).replace('T',' ')}Z</div>
      </div>

      {openPos && <PositionChartModal pos={openPos} onClose={()=>setOpenPos(null)}/>}

      {/* TWEAKS PANEL */}
      <window.TweaksPanel title="Tweaks" defaultOpen={false}>
        <window.TweakSection title="Theme">
          <window.TweakRadio label="Accent" value={t.theme} onChange={v=>setTweak('theme',v)} options={[
            {label:'Green', value:'green'},
            {label:'Amber', value:'amber'},
            {label:'Blue',  value:'blue'},
          ]}/>
          <window.TweakRadio label="Density" value={t.density} onChange={v=>setTweak('density',v)} options={[
            {label:'Sparse',  value:'sparse'},
            {label:'Balanced',value:'balanced'},
            {label:'Dense',   value:'dense'},
          ]}/>
          <window.TweakRadio label="Layout" value={t.layout} onChange={v=>setTweak('layout',v)} options={[
            {label:'Split', value:'split'},
            {label:'Single',value:'single'},
          ]}/>
          <window.TweakRadio label="Mode" value={t.tradingMode} onChange={v=>setTweak('tradingMode',v)} options={[
            {label:'Live', value:'live'},
            {label:'Test', value:'testnet'},
          ]}/>
        </window.TweakSection>
        <window.TweakSection title="HUD">
          <window.TweakToggle label="Tactical Background" value={t.tacticalBg} onChange={v=>setTweak('tacticalBg',v)} hint="Scanlines, grid, drift glow"/>
          <window.TweakToggle label="HUD Overlays" value={t.hudOverlays} onChange={v=>setTweak('hudOverlays',v)} hint="Reticles, scanline texture, brackets"/>
        </window.TweakSection>
        <window.TweakSection title="Sim">
          <window.TweakSlider label="Speed" value={t.simSpeed} min={0.5} max={4} step={0.5} onChange={v=>setTweak('simSpeed',v)}/>
          <window.TweakButton label={running?'Stop Engine':'Start Engine'} onClick={()=>running?handleStop():handleStart()}/>
          <window.TweakButton label="Reset Session" onClick={()=>{ setPositions(SEED_POSITIONS); setTrades(SEED_HISTORY); setRunning(true); }}/>
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
}

function RiskBar({ label, value, max, unit, amber }){
  const pct = Math.min(100, (value/max)*100);
  const color = amber ? 'var(--amber)' : 'var(--green-soft)';
  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
        <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>{label}</span>
        <span className="mono" style={{fontSize:11,color,fontWeight:700}}>{value}{unit} <span style={{color:'var(--fg-4)'}}>/ {max}{unit}</span></span>
      </div>
      <div style={{position:'relative',height:6,borderRadius:3,background:'rgba(0,0,0,.5)',overflow:'hidden',border:'1px solid var(--border-soft)'}}>
        <div style={{height:'100%',width:pct+'%',background:`linear-gradient(90deg, ${color}, color-mix(in oklch, ${color} 60%, transparent))`,boxShadow:`0 0 10px ${color}`,transition:'width .6s ease'}}/>
      </div>
    </div>
  );
}

window.StatusApp = StatusApp;
if (!window.__BOT_SHELL__) ReactDOM.createRoot(document.getElementById('root')).render(<StatusApp/>);

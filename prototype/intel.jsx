// ── INTEL — Macro / Regime / Liquidations / News ───────────
const SS = window.SS;

// ── Synthetic data ──────────────────────────────────────────
const FUNDING_SEED = [
  { sym:'BTC',  oi: 23.4e9, oiΔ:  2.1, fund: 0.0118, mark: 65120, change24:  1.42 },
  { sym:'ETH',  oi: 11.8e9, oiΔ: -0.6, fund: 0.0094, mark: 3198,  change24: -0.32 },
  { sym:'SOL',  oi:  3.62e9,oiΔ:  4.7, fund: 0.0240, mark: 141.05,change24:  0.81 },
  { sym:'BNB',  oi:  1.94e9,oiΔ:  0.4, fund: 0.0061, mark: 572.4, change24:  0.22 },
  { sym:'XRP',  oi:  1.41e9,oiΔ: -1.8, fund: 0.0042, mark: 0.524, change24: -0.91 },
  { sym:'TON',  oi:  0.82e9,oiΔ:  6.1, fund: 0.0180, mark: 6.84,  change24:  2.10 },
  { sym:'AVAX', oi:  0.51e9,oiΔ: -0.9, fund: 0.0072, mark: 34.18, change24:  1.10 },
  { sym:'LINK', oi:  0.46e9,oiΔ:  1.1, fund: 0.0085, mark: 14.86, change24:  0.50 },
  { sym:'INJ',  oi:  0.31e9,oiΔ:  3.2, fund: 0.0301, mark: 24.18, change24:  3.40 },
  { sym:'DOGE', oi:  0.62e9,oiΔ: -2.4, fund: 0.0035, mark: 0.134, change24: -0.97 },
];

const LIQ_SEED = [
  { sym:'BTC',  longs:  4.2e6, shorts: 12.8e6, ts: 14*60+12 },
  { sym:'ETH',  longs:  1.8e6, shorts:  6.4e6, ts: 13*60+58 },
  { sym:'SOL',  longs:  0.9e6, shorts:  3.1e6, ts: 13*60+44 },
  { sym:'BTC',  longs:  2.1e6, shorts:  0.8e6, ts: 13*60+22 },
  { sym:'TON',  longs:  0.4e6, shorts:  1.9e6, ts: 13*60+10 },
  { sym:'INJ',  longs:  0.2e6, shorts:  0.7e6, ts: 12*60+58 },
  { sym:'ETH',  longs:  0.3e6, shorts:  2.4e6, ts: 12*60+44 },
  { sym:'AVAX', longs:  0.1e6, shorts:  0.5e6, ts: 12*60+22 },
];

const NEWS_SEED = [
  { id:'n1', tag:'MACRO',  pri:'HIGH', t:'14:32',  src:'Bloomberg', headline:'Fed minutes signal patience on rate cuts; market prices in 2 cuts by Q4', impact:'bullish' },
  { id:'n2', tag:'CHAIN',  pri:'MED',  t:'14:11',  src:'Coindesk',  headline:'BTC ETF inflows hit $312M in single session, breaking 6-day outflow streak', impact:'bullish' },
  { id:'n3', tag:'REG',    pri:'HIGH', t:'13:58',  src:'Reuters',   headline:'SEC delays decision on ETH staking ETF amendment to mid-Q3', impact:'neutral' },
  { id:'n4', tag:'WHALE',  pri:'LOW',  t:'13:42',  src:'WhaleAlert',headline:'2,400 BTC moved from cold wallet (origin: 2017) to Coinbase deposit', impact:'bearish' },
  { id:'n5', tag:'CHAIN',  pri:'MED',  t:'13:21',  src:'Coindesk',  headline:'Solana validator count crosses 1,950; Jito MEV revenue up 24% week-over-week', impact:'bullish' },
  { id:'n6', tag:'MACRO',  pri:'MED',  t:'12:55',  src:'WSJ',       headline:'DXY softens to 103.4 as 10Y yields drop 6bp on weaker ISM print', impact:'bullish' },
  { id:'n7', tag:'EXCH',   pri:'LOW',  t:'12:18',  src:'TheBlock',  headline:'Binance lists PERP for new L2 token; OI builds $112M in first 4h', impact:'neutral' },
  { id:'n8', tag:'WHALE',  pri:'HIGH', t:'11:44',  src:'Arkham',    headline:'Mt. Gox trustee wallet shifts 47K BTC — likely creditor distribution prep', impact:'bearish' },
];

const SESSIONS = [
  { name:'TOKYO',   open: 0,  close: 9,  active: false, color:'#60a5fa' },
  { name:'LONDON',  open: 8,  close: 17, active: true,  color:'#fbbf24' },
  { name:'NEW YORK',open: 13, close: 22, active: true,  color:'#22c55e' },
];

// ── BTC Dominance Dial ──────────────────────────────────────
function DominanceDial({ value, label, range, color, sub }){
  const pct = (value - range[0]) / (range[1] - range[0]);
  const angle = -135 + pct * 270;
  const r = 90;
  const cx = 0, cy = 0;
  // arc generator
  const arc = (start, end) => {
    const s = (start * Math.PI)/180, e = (end * Math.PI)/180;
    const x1 = cx + r * Math.cos(s), y1 = cy + r * Math.sin(s);
    const x2 = cx + r * Math.cos(e), y2 = cy + r * Math.sin(e);
    const large = (end - start) > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };
  return (
    <div style={{position:'relative',width:'100%',aspectRatio:'1.6/1',maxWidth:340,margin:'0 auto'}}>
      <svg viewBox="-110 -110 220 130" style={{width:'100%',height:'100%'}}>
        {/* track */}
        <path d={arc(-180+45, 45)} stroke="rgba(255,255,255,.06)" strokeWidth="6" fill="none" strokeLinecap="round"/>
        {/* tick marks */}
        {Array.from({length: 11}).map((_,i)=>{
          const a = (-135 + i*27) * Math.PI/180;
          const x1 = Math.cos(a)*82, y1 = Math.sin(a)*82;
          const x2 = Math.cos(a)*98, y2 = Math.sin(a)*98;
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(255,255,255,.12)" strokeWidth=".7"/>;
        })}
        {/* fill */}
        <path d={arc(-135, angle)} stroke={color} strokeWidth="6" fill="none" strokeLinecap="round" style={{filter:`drop-shadow(0 0 6px ${color})`}}/>
        {/* needle */}
        <g transform={`rotate(${angle})`}>
          <line x1="0" y1="0" x2={r-8} y2="0" stroke={color} strokeWidth="2.4" strokeLinecap="round"/>
          <circle cx={r-8} cy={0} r="3" fill={color} style={{filter:`drop-shadow(0 0 4px ${color})`}}/>
        </g>
        <circle r="6" fill="rgba(0,0,0,.6)" stroke={color} strokeWidth="1.5"/>
        {/* range labels */}
        <text x="-94" y="14" fill="var(--fg-4)" fontSize="7" fontFamily="JetBrains Mono,monospace">{range[0]}%</text>
        <text x="78"  y="14" fill="var(--fg-4)" fontSize="7" fontFamily="JetBrains Mono,monospace">{range[1]}%</text>
      </svg>
      <div style={{position:'absolute',inset:0,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'flex-end',pointerEvents:'none',paddingBottom:'8%'}}>
        <div className="mono" style={{fontSize:9,letterSpacing:'.2em',color:'var(--fg-4)',textTransform:'uppercase',marginBottom:2}}>{label}</div>
        <div style={{fontFamily:'Share Tech Mono,monospace',fontSize:32,letterSpacing:'.04em',color,fontWeight:700,lineHeight:1}}>{value.toFixed(2)}%</div>
        <div className="mono" style={{fontSize:10,color:'var(--fg-3)',marginTop:4}}>{sub}</div>
      </div>
    </div>
  );
}

// ── Regime Tape (vertical/horizontal bar w/ labels) ─────────
function RegimeTape({ score, label, ranges, color }){
  // ranges: array of {label, min, max, color}
  const pct = Math.max(0, Math.min(100, ((score - ranges[0].min)/(ranges[ranges.length-1].max - ranges[0].min))*100));
  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
        <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>{label}</span>
        <span className="mono" style={{fontSize:11,fontWeight:700,color}}>{score.toFixed(0)}</span>
      </div>
      <div style={{position:'relative',height:14,borderRadius:3,overflow:'hidden',border:'1px solid var(--border-soft)',background:'rgba(0,0,0,.4)',display:'flex'}}>
        {ranges.map((r,i)=>{
          const w = ((r.max - r.min)/(ranges[ranges.length-1].max - ranges[0].min))*100;
          return <div key={i} style={{width:w+'%',background:r.color,opacity:.25}}/>;
        })}
        <div style={{position:'absolute',top:-2,bottom:-2,left:'calc('+pct+'% - 2px)',width:4,background:color,boxShadow:`0 0 8px ${color}`,borderRadius:1}}/>
      </div>
      <div style={{display:'flex',justifyContent:'space-between',marginTop:4}}>
        {ranges.map((r,i)=>(
          <span key={i} className="mono" style={{fontSize:8,color:'var(--fg-4)',letterSpacing:'.16em',textTransform:'uppercase'}}>{r.label}</span>
        ))}
      </div>
    </div>
  );
}

// ── Funding heat row ────────────────────────────────────────
function FundingRow({ row }){
  const fundColor = row.fund > 0.02 ? 'var(--red-2)' : row.fund > 0.01 ? 'var(--amber)' : row.fund > 0 ? 'var(--green-soft)' : 'var(--blue)';
  const oiColor = row.oiΔ > 2 ? 'var(--green-soft)' : row.oiΔ < -1 ? 'var(--red-2)' : 'var(--fg-2)';
  // max funding visualized at 0.04% (annualized danger zone)
  const fundPct = Math.max(0, Math.min(100, (row.fund / 0.04)*100));
  return (
    <div className="watch-row" style={{padding:'10px 4px'}}>
      <div style={{display:'flex',alignItems:'center',gap:10,flex:'0 0 70px'}}>
        <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:13,letterSpacing:'.06em'}}>{row.sym}</span>
      </div>
      <div style={{flex:'0 0 100px'}} className="mono">
        <span style={{fontSize:12,color:'var(--fg)'}}>{SS.fmtPrice(row.mark)}</span>
        <span style={{fontSize:10,color: row.change24>=0?'var(--green-soft)':'var(--red-2)',marginLeft:6}}>{SS.fmtPct(row.change24,1)}</span>
      </div>
      <div style={{flex:1,display:'flex',alignItems:'center',gap:8}}>
        <div style={{flex:1,position:'relative',height:5,borderRadius:2,background:'rgba(255,255,255,.05)',overflow:'hidden'}}>
          <div style={{position:'absolute',top:0,bottom:0,left:0,width:fundPct+'%',background:fundColor,boxShadow:`0 0 6px ${fundColor}`}}/>
        </div>
        <span className="mono" style={{fontSize:11,color:fundColor,fontWeight:700,minWidth:62,textAlign:'right'}}>{(row.fund*100).toFixed(4)}%</span>
      </div>
      <div style={{flex:'0 0 90px',textAlign:'right'}} className="mono">
        <div style={{fontSize:11,color:'var(--fg-2)'}}>${SS.fmtNum(row.oi).replace(/\$/,'')}</div>
        <div style={{fontSize:9,color:oiColor}}>{SS.fmtPct(row.oiΔ,1)}</div>
      </div>
    </div>
  );
}

// ── Liquidation Heatmap (synthetic price grid) ──────────────
function LiqHeatmap({ symbol }){
  // Bucket levels around current price; each bucket has long+short notional
  const data = useMemo(()=>{
    const center = 65120;
    const buckets = 14;
    const step = 0.005; // .5% per bucket
    return Array.from({length:buckets}).map((_,i)=>{
      const offset = (i - buckets/2) * step;
      const price = center * (1 + offset);
      // shorts cluster above price, longs below (typical)
      const shortHeat = offset > 0 ? Math.abs(Math.sin(offset*100)*0.7 + Math.random()*0.4) : Math.random()*0.25;
      const longHeat  = offset < 0 ? Math.abs(Math.cos(offset*120)*0.7 + Math.random()*0.4) : Math.random()*0.20;
      return { offset, price, shortHeat, longHeat };
    }).reverse();
  }, [symbol]);
  const max = Math.max(...data.flatMap(d=>[d.shortHeat,d.longHeat]));
  return (
    <div style={{padding:'12px 2px'}}>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:8}}>
        <span className="mono" style={{fontSize:9,color:'var(--red-2)',letterSpacing:'.18em',textTransform:'uppercase'}}>◀ SHORT LIQUIDATIONS</span>
        <span className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>{symbol} · price ladder</span>
        <span className="mono" style={{fontSize:9,color:'var(--green-soft)',letterSpacing:'.18em',textTransform:'uppercase'}}>LONG LIQUIDATIONS ▶</span>
      </div>
      <div style={{display:'flex',flexDirection:'column',gap:2,fontFamily:'JetBrains Mono,monospace',fontSize:10}}>
        {data.map((d,i)=>{
          const sw = (d.shortHeat/max)*100;
          const lw = (d.longHeat/max)*100;
          const isCurrent = Math.abs(d.offset) < 0.003;
          return (
            <div key={i} style={{display:'grid',gridTemplateColumns:'1fr 90px 1fr',alignItems:'center',gap:8,padding:isCurrent?'2px 0':'0',background:isCurrent?'rgba(251,191,36,.08)':'transparent',borderRadius:isCurrent?4:0}}>
              <div style={{display:'flex',justifyContent:'flex-end',height:14,position:'relative'}}>
                <div style={{
                  width: sw+'%',
                  background:`linear-gradient(90deg, transparent, rgba(248,113,113, ${0.25+0.55*(d.shortHeat/max)}))`,
                  border:`1px solid rgba(248,113,113,${0.4+0.4*(d.shortHeat/max)})`,
                  borderRight:'none',
                  height:14, borderRadius:'2px 0 0 2px',
                }}/>
              </div>
              <div className="mono" style={{textAlign:'center',fontSize:10,fontWeight:isCurrent?800:500,color:isCurrent?'var(--amber)':'var(--fg-3)'}}>
                {isCurrent && <span style={{marginRight:4}}>◉</span>}
                ${d.price.toFixed(0)}
              </div>
              <div style={{display:'flex',height:14,position:'relative'}}>
                <div style={{
                  width: lw+'%',
                  background:`linear-gradient(90deg, rgba(34,197,94, ${0.25+0.55*(d.longHeat/max)}), transparent)`,
                  border:`1px solid rgba(34,197,94,${0.4+0.4*(d.longHeat/max)})`,
                  borderLeft:'none',
                  height:14, borderRadius:'0 2px 2px 0',
                }}/>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── News feed item ─────────────────────────────────────────
function NewsItem({ item }){
  const [open, setOpen] = useState(false);
  const tagColors = { MACRO:'blue', REG:'red', CHAIN:'green', WHALE:'amber', EXCH:'purple' };
  const priColor = item.pri==='HIGH'?'var(--red-2)':item.pri==='MED'?'var(--amber)':'var(--fg-3)';
  const impactColor = item.impact==='bullish'?'var(--green-soft)':item.impact==='bearish'?'var(--red-2)':'var(--blue)';
  return (
    <div className={`hist ${open?'expanded':''}`} onClick={()=>setOpen(!open)}>
      <div style={{display:'flex',alignItems:'center',gap:10}}>
        <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.14em',width:42,flexShrink:0}}>{item.t}</span>
        <SS.Chip kind={tagColors[item.tag]||''} style={{flexShrink:0,fontSize:9}}>{item.tag}</SS.Chip>
        <span style={{flexShrink:0,fontSize:9,color:priColor,fontWeight:700,letterSpacing:'.16em'}} className="mono">▲ {item.pri}</span>
        <span style={{flex:1,fontSize:12,color:'var(--fg-2)',lineHeight:1.4,minWidth:0,textWrap:'pretty'}}>{item.headline}</span>
        <span className="mono" style={{fontSize:10,color:impactColor,fontWeight:700,flexShrink:0,letterSpacing:'.16em',textTransform:'uppercase'}}>{item.impact}</span>
      </div>
      {open && (
        <div style={{marginTop:10,paddingTop:10,borderTop:'1px solid var(--border-soft)',display:'flex',gap:14,fontFamily:'JetBrains Mono,monospace',fontSize:11,color:'var(--fg-3)'}}>
          <span>SRC · {item.src}</span>
          <span>WIRE · {item.t} UTC</span>
          <span style={{color:impactColor}}>BIAS · {item.impact.toUpperCase()}</span>
          <span style={{marginLeft:'auto',color:'var(--accent)'}}>OPEN ARTICLE →</span>
        </div>
      )}
    </div>
  );
}

// ── Session clock strip ─────────────────────────────────────
function SessionStrip(){
  const now = new Date();
  const utcHour = now.getUTCHours() + now.getUTCMinutes()/60;
  const cellW = 100/24;
  return (
    <div>
      <div style={{position:'relative',height:60,border:'1px solid var(--border-soft)',borderRadius:6,background:'rgba(0,0,0,.4)',overflow:'hidden'}}>
        {/* Hour grid */}
        {Array.from({length:24}).map((_,i)=>(
          <div key={i} style={{position:'absolute',top:0,bottom:0,left:`${i*cellW}%`,width:'1px',background:'rgba(255,255,255,.04)'}}/>
        ))}
        {/* Sessions */}
        {SESSIONS.map((s,i)=>{
          const left = (s.open/24)*100;
          const width = ((s.close - s.open)/24)*100;
          return (
            <div key={s.name} style={{
              position:'absolute',
              top: 6 + i*16,
              height:14,
              left:`${left}%`,
              width:`${width}%`,
              background: s.active ? `linear-gradient(90deg, ${s.color}33, ${s.color}88)` : `${s.color}22`,
              border: `1px solid ${s.color}${s.active?'cc':'55'}`,
              borderRadius:3,
              display:'flex',alignItems:'center',padding:'0 6px',
              boxShadow: s.active ? `0 0 8px ${s.color}66` : 'none',
            }}>
              <span className="mono" style={{fontSize:9,letterSpacing:'.18em',color:s.active?s.color:'var(--fg-3)',fontWeight:700}}>{s.name}</span>
            </div>
          );
        })}
        {/* Now indicator */}
        <div style={{position:'absolute',top:0,bottom:0,left:`${(utcHour/24)*100}%`,width:2,background:'var(--accent)',boxShadow:'0 0 8px var(--accent)',zIndex:2}}>
          <div style={{position:'absolute',top:-6,left:-5,width:12,height:12,borderRadius:6,background:'var(--accent)',boxShadow:'0 0 8px var(--accent)'}}/>
        </div>
      </div>
      <div style={{display:'flex',justifyContent:'space-between',marginTop:6,fontFamily:'JetBrains Mono,monospace',fontSize:9,color:'var(--fg-4)',letterSpacing:'.14em'}}>
        <span>00 UTC</span><span>06</span><span>12 ◉ {utcHour.toFixed(0).padStart(2,'0')}:{String(now.getUTCMinutes()).padStart(2,'0')}</span><span>18</span><span>24</span>
      </div>
    </div>
  );
}

// ── AI commentary "terminal" ────────────────────────────────
function AICommentary(){
  const lines = [
    { t:'PRIMARY',  text:'BTC reclaiming 64.5K with rising spot CVD; ETF inflow flip is structural.', conf: 78 },
    { t:'CAVEAT',   text:'Mt. Gox tranche flagged — distribution overhang next 7-14 sessions.', conf: 62 },
    { t:'OPP',      text:'Alts (TON, INJ, SOL) showing OI expansion w/ funding under 0.025% — clean longs.', conf: 71 },
    { t:'HEDGE',    text:'10Y yield pivot < 4.20% would unlock risk-on; >4.40% reverses thesis.', conf: 68 },
    { t:'TIMING',   text:'NY session momentum window 14:30-16:00 UTC has +1.4σ historical edge.', conf: 74 },
  ];
  return (
    <div style={{padding:'14px 18px',background:'rgba(0,0,0,.45)',borderTop:'1px solid var(--border-soft)',fontFamily:'JetBrains Mono,monospace'}}>
      <div style={{fontSize:11,color:'var(--accent)',marginBottom:10,opacity:.85}}>
        {`> ai-analyst.exec --regime --window=24h`}<span className="cursor-blink">_</span>
      </div>
      <div style={{display:'flex',flexDirection:'column',gap:10}}>
        {lines.map((l,i)=>(
          <div key={i} style={{display:'flex',gap:10,alignItems:'flex-start',fontSize:12,lineHeight:1.45,color:'var(--fg-2)'}}>
            <span className="mono" style={{fontSize:9,color:'var(--accent)',letterSpacing:'.18em',fontWeight:800,paddingTop:3,minWidth:62}}>{l.t}</span>
            <span style={{flex:1,color:'var(--fg)'}}>{l.text}</span>
            <span className="mono" style={{fontSize:10,color: l.conf>=70?'var(--green-soft)':l.conf>=60?'var(--amber)':'var(--fg-3)',fontWeight:700,minWidth:38,textAlign:'right'}}>{l.conf}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Live mini-ticker (header strip values) ──────────────────
function MacroTicker({ values }){
  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(6, minmax(0,1fr))',gap:0,border:'1px solid var(--border-soft)',borderRadius:8,overflow:'hidden',background:'rgba(0,0,0,.35)'}}>
      {values.map((v,i)=>(
        <div key={i} style={{padding:'10px 14px',borderRight: i<values.length-1?'1px solid var(--border-soft)':'none'}}>
          <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:3}}>{v.label}</div>
          <div className="mono" style={{fontSize:13,fontWeight:700,color:v.color||'var(--fg)'}}>{v.value}</div>
          {v.delta != null && <div className="mono" style={{fontSize:9,color:v.delta>=0?'var(--green-soft)':'var(--red-2)',fontWeight:600}}>{SS.fmtPct(v.delta,2)}</div>}
        </div>
      ))}
    </div>
  );
}

// ── App ─────────────────────────────────────────────────────
function App(){
  const [t, setTweak] = window.useTweaks({
    ...SS.SHARED_TWEAK_DEFAULTS,
    showAI: true,
    liqSymbol: 'BTC',
  });
  useEffect(()=>{ SS.applyTweaks(t, 'blue'); }, [t]);

  const [now, setNow] = useState(Date.now());
  const [funding, setFunding] = useState(FUNDING_SEED);
  const [news, setNews] = useState(NEWS_SEED);
  const [btcDom, setBtcDom] = useState(54.32);
  const [usdtDom, setUsdtDom] = useState(4.12);
  const [fearGreed, setFearGreed] = useState(64);

  useEffect(()=>{
    const id = setInterval(()=>{
      setNow(Date.now());
      setBtcDom(d => d + (Math.random()-0.5)*0.04);
      setUsdtDom(d => d + (Math.random()-0.5)*0.02);
      setFearGreed(f => Math.max(5, Math.min(95, f + (Math.random()-0.5)*1.2)));
      setFunding(prev => prev.map(r => ({
        ...r,
        fund: Math.max(-0.01, r.fund + (Math.random()-0.5)*0.0008),
        mark: r.mark * (1 + (Math.random()-0.5)*0.0008),
        oiΔ: r.oiΔ + (Math.random()-0.5)*0.15,
      })));
    }, 1500/(t.simSpeed||1));
    return ()=>clearInterval(id);
  }, [t.simSpeed]);

  const totalLongLiq = LIQ_SEED.reduce((a,l)=>a+l.longs,0);
  const totalShortLiq = LIQ_SEED.reduce((a,l)=>a+l.shorts,0);

  return (
    <div className="shell">
      <SS.Topbar active="intel" now={now}/>

      <SS.PageHead
        icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="var(--blue)" strokeWidth="1.7"/>
          <path d="M12 3 v18 M3 12 h18" stroke="var(--blue)" strokeWidth="1.2" strokeOpacity=".5"/>
          <ellipse cx="12" cy="12" rx="9" ry="4" stroke="var(--blue)" strokeWidth="1.2" strokeOpacity=".7"/>
          <circle cx="12" cy="12" r="2" fill="var(--blue)"/>
        </svg>}
        title="Intel"
        subtitle="macro regime · funding · liquidations · catalysts"
        badges={<>
          <SS.Chip kind="blue">REGIME · BULL TREND</SS.Chip>
          <SS.Chip kind="green">RISK-ON</SS.Chip>
          <SS.Chip>UPDATED {new Date(now).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</SS.Chip>
        </>}
      />

      {/* Macro ticker strip */}
      <div style={{marginBottom:18}}>
        <MacroTicker values={[
          { label:'BTC', value:'$65,120', delta: 1.42, color:'var(--fg)' },
          { label:'ETH', value:'$3,198',  delta: -.32, color:'var(--fg)' },
          { label:'DXY', value:'103.41',  delta: -.18, color:'var(--blue)' },
          { label:'10Y', value:'4.184%',  delta: -.06, color:'var(--blue)' },
          { label:'GOLD',value:'$2,408',  delta:  .22, color:'var(--amber)' },
          { label:'VIX', value:'14.32',   delta: -.81, color:'var(--green-soft)' },
        ]}/>
      </div>

      {/* Top: Regime command center */}
      <section className="panel panel-accent" style={{marginBottom:18}}>
        <SS.Reticle/>
        <div className="corner-tag tl">// MACRO-COMMAND</div>
        <div className="corner-tag tr">REGIME ENGINE</div>
        <div style={{padding:'22px 22px 18px'}}>
          <div className="layout-grid" style={{gridTemplateColumns:'1.2fr 1fr',gap:24}}>
            {/* Dominance & dials */}
            <div>
              <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.20em',textTransform:'uppercase',marginBottom:10}}>// DOMINANCE & SENTIMENT</div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:14}}>
                <DominanceDial value={btcDom} label="BTC.D" color="var(--amber-2)" range={[40,70]} sub={btcDom>54?'consolidating':'rotating'}/>
                <DominanceDial value={usdtDom} label="USDT.D" color="var(--green-soft)" range={[3,8]} sub={usdtDom>5?'risk-off':'risk-on'}/>
                <DominanceDial value={fearGreed} label="FEAR · GREED" color={fearGreed>70?'#22c55e':fearGreed>55?'#fbbf24':fearGreed>30?'#f59e0b':'#f87171'} range={[0,100]} sub={fearGreed>74?'extreme greed':fearGreed>55?'greed':fearGreed>45?'neutral':fearGreed>25?'fear':'extreme fear'}/>
              </div>
            </div>
            {/* Regime tapes */}
            <div>
              <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.20em',textTransform:'uppercase',marginBottom:10}}>// REGIME CLASSIFIER</div>
              <div style={{display:'flex',flexDirection:'column',gap:14}}>
                <RegimeTape score={72} label="Trend Strength" color="var(--green-soft)" ranges={[
                  { label:'CHOP', min:0, max:30, color:'#f87171' },
                  { label:'WEAK', min:30, max:55, color:'#fbbf24' },
                  { label:'TREND',min:55, max:80, color:'#22c55e' },
                  { label:'STRONG',min:80,max:100,color:'#00ffaa' },
                ]}/>
                <RegimeTape score={48} label="Volatility (ATR%)" color="var(--amber)" ranges={[
                  { label:'LOW',  min:0, max:30, color:'#60a5fa' },
                  { label:'NORM', min:30,max:60, color:'#22c55e' },
                  { label:'HIGH', min:60,max:85, color:'#fbbf24' },
                  { label:'EXT',  min:85,max:100,color:'#f87171' },
                ]}/>
                <RegimeTape score={68} label="Risk Appetite" color="var(--green-soft)" ranges={[
                  { label:'OFF',  min:0, max:35, color:'#f87171' },
                  { label:'NEUT', min:35,max:55, color:'#fbbf24' },
                  { label:'ON',   min:55,max:80, color:'#22c55e' },
                  { label:'EUPH', min:80,max:100,color:'#00ffaa' },
                ]}/>
                <RegimeTape score={31} label="Correlation" color="var(--blue)" ranges={[
                  { label:'DECOR',min:0, max:35, color:'#22c55e' },
                  { label:'NORM', min:35,max:65, color:'#60a5fa' },
                  { label:'HIGH', min:65,max:85, color:'#fbbf24' },
                  { label:'CRISIS',min:85,max:100,color:'#f87171' },
                ]}/>
              </div>
            </div>
          </div>

          <div style={{marginTop:18,paddingTop:14,borderTop:'1px solid var(--border-soft)'}}>
            <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.20em',textTransform:'uppercase',marginBottom:10}}>// SESSION CLOCK · LIVE</div>
            <SessionStrip/>
          </div>
        </div>
      </section>

      {/* Main Grid */}
      <div className="layout-grid">
        <div className="col">
          {/* Funding & OI */}
          <section className="panel">
            <SS.SectionHead title="Funding & Open Interest" right={<>
              <SS.Chip kind="amber">⚠ {funding.filter(f=>f.fund>0.02).length} OVERHEATED</SS.Chip>
              <SS.Chip>{funding.length} PERPS</SS.Chip>
            </>}/>
            <div style={{padding:'10px 18px 14px'}}>
              <div style={{display:'grid',gridTemplateColumns:'70px 100px 1fr 90px',gap:8,padding:'4px 4px 8px',borderBottom:'1px solid var(--border-soft)',marginBottom:6}}>
                <span className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em'}}>SYM</span>
                <span className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em'}}>MARK · 24H</span>
                <span className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em'}}>FUNDING (ANNUAL)</span>
                <span className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textAlign:'right'}}>OI · 24H Δ</span>
              </div>
              {funding.map(r => <FundingRow key={r.sym} row={r}/>)}
            </div>
          </section>

          {/* Liquidations */}
          <section className="panel">
            <SS.SectionHead title="Liquidation Heatmap" right={<>
              <SS.Chip kind="red">L · {SS.fmtMoney(totalLongLiq/1e6,1)}M</SS.Chip>
              <SS.Chip kind="green">S · {SS.fmtMoney(totalShortLiq/1e6,1)}M</SS.Chip>
              <SS.Chip>4H WINDOW</SS.Chip>
            </>}/>
            <div style={{padding:'4px 18px 14px'}}>
              <div style={{display:'flex',gap:6,marginBottom:8}}>
                {['BTC','ETH','SOL','TON'].map(s => (
                  <button
                    key={s}
                    className={`btn ${t.liqSymbol===s?'btn-cyan':''}`}
                    style={{padding:'6px 12px',fontSize:10}}
                    onClick={()=>setTweak('liqSymbol',s)}
                  >{s}</button>
                ))}
              </div>
              <LiqHeatmap symbol={t.liqSymbol}/>
              <div style={{marginTop:14,paddingTop:12,borderTop:'1px solid var(--border-soft)'}}>
                <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// RECENT LIQUIDATIONS · TAPE</div>
                <div style={{display:'flex',flexDirection:'column',gap:4,fontFamily:'JetBrains Mono,monospace',fontSize:11}}>
                  {LIQ_SEED.slice(0,6).map((l,i)=>{
                    const total = l.longs + l.shorts;
                    const longHeavy = l.longs > l.shorts;
                    return (
                      <div key={i} style={{display:'grid',gridTemplateColumns:'48px 56px 1fr 80px',gap:8,padding:'4px 8px',background:'rgba(0,0,0,.3)',borderRadius:4,border:'1px solid var(--border-soft)'}}>
                        <span style={{color:'var(--fg-4)'}}>{Math.floor(l.ts/60).toString().padStart(2,'0')}:{(l.ts%60).toString().padStart(2,'0')}</span>
                        <span style={{color:'var(--fg)',fontWeight:700,letterSpacing:'.06em'}}>{l.sym}</span>
                        <span style={{color:longHeavy?'var(--red-2)':'var(--green-soft)',fontWeight:600,letterSpacing:'.04em'}}>{longHeavy?'▼ LONGS WIPED':'▲ SHORTS WIPED'}</span>
                        <span style={{textAlign:'right',color:'var(--fg)',fontWeight:700}}>${SS.fmtNum(total).replace('$','')}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </section>
        </div>

        <div className="col">
          {/* News / Catalysts */}
          <section className="panel">
            <SS.Reticle/>
            <SS.SectionHead title="Catalyst Wire" right={<>
              <SS.Chip kind="red">{news.filter(n=>n.pri==='HIGH').length} HIGH</SS.Chip>
              <SS.Chip kind="amber">// LIVE FEED</SS.Chip>
            </>}/>
            <div style={{padding:'12px 18px',display:'flex',flexDirection:'column',gap:6,maxHeight:520,overflowY:'auto'}}>
              {news.map(n => <NewsItem key={n.id} item={n}/>)}
            </div>
          </section>

          {/* AI Analyst */}
          <section className="panel">
            <SS.SectionHead title="AI Analyst · Regime Read" right={<>
              <SS.Chip kind="accent">CONF · 71</SS.Chip>
              <SS.Chip>HAIKU 4.5</SS.Chip>
            </>}/>
            {t.showAI ? <AICommentary/> : (
              <div style={{padding:30,textAlign:'center',color:'var(--fg-4)',fontFamily:'JetBrains Mono,monospace',fontSize:11,letterSpacing:'.18em',textTransform:'uppercase'}}>// AI commentary disabled in tweaks</div>
            )}
          </section>

          {/* Quick state */}
          <section className="panel">
            <SS.SectionHead title="Position · Bias Map" right={<SS.Chip kind="blue">5 SLOTS</SS.Chip>}/>
            <div style={{padding:'14px 18px',display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
              <div className="metric-tile">
                <div className="metric-label">Bot Bias</div>
                <div className="metric-value" style={{color:'var(--green-soft)'}}>+ LONG</div>
                <div className="metric-sub">3 of 5 slots, net +$34.87</div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">Confluence Floor</div>
                <div className="metric-value">≥ 7.0</div>
                <div className="metric-sub">strict gate active</div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">Active Setups</div>
                <div className="metric-value hud-glow">OB · FVG · BOS</div>
                <div className="metric-sub">priority weighted</div>
              </div>
              <div className="metric-tile">
                <div className="metric-label">BTC Veto</div>
                <div className="metric-value" style={{color:'var(--green-soft)'}}>● CLEAR</div>
                <div className="metric-sub">no impulse moves &gt; 2.5σ</div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <SS.FooterStatus now={now} latency={38}/>

      <window.TweaksPanel title="Tweaks" defaultOpen={false}>
        <SS.SharedTweaksControls t={t} setTweak={setTweak}/>
        <window.TweakSection title="Intel">
          <window.TweakToggle label="AI Commentary" value={t.showAI} onChange={v=>setTweak('showAI',v)}/>
          <window.TweakRadio label="Liq Symbol" value={t.liqSymbol} onChange={v=>setTweak('liqSymbol',v)} options={[
            {label:'BTC',value:'BTC'},
            {label:'ETH',value:'ETH'},
            {label:'SOL',value:'SOL'},
            {label:'TON',value:'TON'},
          ]}/>
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

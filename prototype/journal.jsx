// ── JOURNAL — closed trade analytics, stats, MAE/MFE, notes ─
const SS = window.SS;

const TRADES_SEED = [
  { id:'t1', sym:'AVAX/USDT', dir:'LONG',  setup:'OB+FVG',     pnl: 23.18, pnl_pct:2.21, rr: 1.74, mae:0.32, mfe:2.45, dur:48,  exit:'tp2_hit',       date:'2026-04-30', tags:['A+','clean'],   conf:81 },
  { id:'t2', sym:'LINK/USDT', dir:'SHORT', setup:'CHoCH',      pnl: 11.40, pnl_pct:1.61, rr: 1.42, mae:0.18, mfe:1.71, dur:18,  exit:'tp1_hit',       date:'2026-04-30', tags:['scalp'],        conf:74 },
  { id:'t3', sym:'DOGE/USDT', dir:'LONG',  setup:'BOS',        pnl:-6.20,  pnl_pct:-0.97,rr:-1.00, mae:1.10, mfe:0.42, dur:24,  exit:'stop_loss',     date:'2026-04-30', tags:['chase'],        conf:69 },
  { id:'t4', sym:'ARB/USDT',  dir:'LONG',  setup:'OB-RETEST',  pnl: 18.60, pnl_pct:2.86, rr: 1.91, mae:0.51, mfe:3.12, dur:90,  exit:'trailing_stop', date:'2026-04-30', tags:['A+','swing'],   conf:79 },
  { id:'t5', sym:'BNB/USDT',  dir:'SHORT', setup:'BREAKER',    pnl: 5.10,  pnl_pct:0.40, rr: 0.25, mae:0.21, mfe:0.92, dur:45,  exit:'breakeven_stop',date:'2026-04-30', tags:['low-vol'],      conf:71 },
  { id:'t6', sym:'INJ/USDT',  dir:'LONG',  setup:'FVG-FILL',   pnl: 14.92, pnl_pct:2.40, rr: 1.60, mae:0.41, mfe:2.62, dur:40,  exit:'tp1_hit',       date:'2026-04-29', tags:['clean'],        conf:76 },
  { id:'t7', sym:'BTC/USDT',  dir:'LONG',  setup:'OB+FVG',     pnl: 41.20, pnl_pct:1.95, rr: 2.10, mae:0.62, mfe:2.84, dur:142, exit:'tp2_hit',       date:'2026-04-29', tags:['A+'],           conf:84 },
  { id:'t8', sym:'SOL/USDT',  dir:'SHORT', setup:'LIQ-SWEEP',  pnl: 8.40,  pnl_pct:1.18, rr: 1.20, mae:0.31, mfe:1.42, dur:16,  exit:'tp1_hit',       date:'2026-04-29', tags:['scalp'],        conf:78 },
  { id:'t9', sym:'TIA/USDT',  dir:'LONG',  setup:'OB+FVG',     pnl:-9.80,  pnl_pct:-1.42,rr:-1.00, mae:1.42, mfe:0.62, dur:32,  exit:'stop_loss',     date:'2026-04-29', tags:['chase'],        conf:64 },
  { id:'t10',sym:'ETH/USDT',  dir:'LONG',  setup:'BOS',        pnl: 22.18, pnl_pct:1.84, rr: 1.84, mae:0.44, mfe:2.10, dur:78,  exit:'tp1_hit',       date:'2026-04-29', tags:['clean'],        conf:77 },
  { id:'t11',sym:'OP/USDT',   dir:'SHORT', setup:'CHoCH',      pnl:-4.80,  pnl_pct:-0.84,rr:-1.00, mae:0.84, mfe:0.22, dur:21,  exit:'stop_loss',     date:'2026-04-28', tags:['low-conf'],     conf:62 },
  { id:'t12',sym:'BTC/USDT',  dir:'LONG',  setup:'OB-RETEST',  pnl: 33.60, pnl_pct:1.62, rr: 1.62, mae:0.51, mfe:2.18, dur:110, exit:'tp2_hit',       date:'2026-04-28', tags:['A+'],           conf:82 },
  { id:'t13',sym:'AAVE/USDT', dir:'LONG',  setup:'FVG-FILL',   pnl: 7.20,  pnl_pct:0.91, rr: 0.91, mae:0.32, mfe:1.20, dur:38,  exit:'breakeven_stop',date:'2026-04-28', tags:['low-vol'],      conf:70 },
  { id:'t14',sym:'NEAR/USDT', dir:'LONG',  setup:'BREAKER',    pnl:-3.10,  pnl_pct:-0.62,rr:-1.00, mae:0.62, mfe:0.18, dur:14,  exit:'stop_loss',     date:'2026-04-28', tags:['chase'],        conf:58 },
  { id:'t15',sym:'SOL/USDT',  dir:'LONG',  setup:'OB+FVG',     pnl: 28.40, pnl_pct:2.12, rr: 1.94, mae:0.41, mfe:2.62, dur:64,  exit:'tp2_hit',       date:'2026-04-28', tags:['A+','clean'],   conf:80 },
  { id:'t16',sym:'BTC/USDT',  dir:'SHORT', setup:'LIQ-SWEEP',  pnl: 17.80, pnl_pct:0.84, rr: 1.32, mae:0.31, mfe:1.62, dur:52,  exit:'tp1_hit',       date:'2026-04-27', tags:['scalp'],        conf:75 },
  { id:'t17',sym:'INJ/USDT',  dir:'SHORT', setup:'BOS',        pnl:-5.40,  pnl_pct:-0.91,rr:-1.00, mae:0.91, mfe:0.32, dur:18,  exit:'stop_loss',     date:'2026-04-27', tags:[],               conf:67 },
  { id:'t18',sym:'ETH/USDT',  dir:'LONG',  setup:'OB+FVG',     pnl: 19.40, pnl_pct:1.62, rr: 1.62, mae:0.42, mfe:2.04, dur:88,  exit:'tp1_hit',       date:'2026-04-27', tags:['clean'],        conf:78 },
];

function StatTile({ label, value, sub, color, big }){
  return (
    <div className="metric-tile">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{color: color || 'var(--fg)', fontSize: big?22:16}}>{value}</div>
      {sub && <div className="metric-sub" style={{color: color || 'var(--fg-3)', opacity:.7}}>{sub}</div>}
    </div>
  );
}

function EquityCurve({ trades, initial }){
  const W=800, H=180, padL=4, padR=10, padT=10, padB=20;
  const { eqPts, ddPts } = useMemo(()=>{
    let eq = initial, peak = initial;
    const eqPts = [{x:0,y:eq,dd:0}];
    [...trades].reverse().forEach((t,i)=>{
      eq += t.pnl;
      peak = Math.max(peak, eq);
      eqPts.push({x:i+1, y:eq, dd: peak>0 ? -((peak-eq)/peak)*100 : 0});
    });
    return { eqPts, ddPts: eqPts };
  },[trades, initial]);
  const minY = Math.min(...eqPts.map(p=>p.y));
  const maxY = Math.max(...eqPts.map(p=>p.y));
  const yRng = maxY-minY || 1;
  const last = eqPts[eqPts.length-1];
  const isUp = last.y >= initial;
  const stroke = isUp?'var(--green-soft)':'var(--red-2)';

  const xOf = i => padL + (i/(eqPts.length-1))*(W-padL-padR);
  const yOf = y => padT + (1-(y-minY)/yRng)*(H-padT-padB);

  const line = eqPts.map((p,i)=>(i?'L':'M')+xOf(p.x).toFixed(1)+' '+yOf(p.y).toFixed(1)).join(' ');
  const area = line + ` L ${xOf(eqPts.length-1).toFixed(1)} ${H-padB} L ${padL} ${H-padB} Z`;

  // drawdown overlay
  const minDD = Math.min(...eqPts.map(p=>p.dd));
  const ddH = 60;
  const ddYof = dd => H + 8 + (-dd/Math.abs(minDD||1))*ddH;
  const ddPath = eqPts.map((p,i)=>(i?'L':'M')+xOf(p.x).toFixed(1)+' '+ddYof(p.dd).toFixed(1)).join(' ');
  const ddArea = ddPath + ` L ${xOf(eqPts.length-1).toFixed(1)} ${H+8} L ${padL} ${H+8} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H+8+ddH+12}`} style={{width:'100%',height:'auto'}}>
      <defs>
        <linearGradient id="eqg2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity=".25"/>
          <stop offset="100%" stopColor={stroke} stopOpacity="0"/>
        </linearGradient>
        <linearGradient id="ddg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--red-2)" stopOpacity=".05"/>
          <stop offset="100%" stopColor="var(--red-2)" stopOpacity=".25"/>
        </linearGradient>
      </defs>
      {/* gridlines */}
      {[0,.25,.5,.75,1].map(g=>(<line key={g} x1={padL} x2={W-padR} y1={padT+g*(H-padT-padB)} y2={padT+g*(H-padT-padB)} stroke="rgba(255,255,255,.05)" strokeDasharray="2 3"/>))}
      {/* equity */}
      <path d={area} fill="url(#eqg2)"/>
      <path d={line} stroke={stroke} strokeWidth="1.6" fill="none"/>
      <text x={padL+4} y={padT+10} fill="var(--fg-4)" fontSize="9" fontFamily="JetBrains Mono,monospace" letterSpacing=".18em">EQUITY</text>
      <text x={W-padR} y={padT+10} fill={stroke} fontSize="11" fontFamily="JetBrains Mono,monospace" textAnchor="end" fontWeight="700">{SS.fmtMoney(last.y)}</text>
      {/* drawdown panel */}
      <path d={ddArea} fill="url(#ddg)"/>
      <path d={ddPath} stroke="var(--red-2)" strokeWidth="1.2" fill="none" opacity=".8"/>
      <text x={padL+4} y={H+18} fill="var(--fg-4)" fontSize="9" fontFamily="JetBrains Mono,monospace" letterSpacing=".18em">DRAWDOWN</text>
      <text x={W-padR} y={H+18} fill="var(--red-2)" fontSize="11" fontFamily="JetBrains Mono,monospace" textAnchor="end" fontWeight="700">{minDD.toFixed(2)}%</text>
    </svg>
  );
}

function PnLCalendar({ trades }){
  // group by date
  const byDay = useMemo(()=>{
    const map = {};
    trades.forEach(t => { map[t.date] = (map[t.date]||0) + t.pnl; });
    return map;
  }, [trades]);
  const entries = Object.entries(byDay).sort();
  // 4-wide grid
  const max = Math.max(...entries.map(([,v])=>Math.abs(v)));
  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(7,1fr)',gap:4}}>
      {entries.map(([d,v])=>{
        const intensity = Math.abs(v)/max;
        const bg = v>=0 ? `rgba(34,197,94,${0.15+0.55*intensity})` : `rgba(248,113,113,${0.15+0.55*intensity})`;
        const bd = v>=0 ? `rgba(34,197,94,.5)` : `rgba(248,113,113,.5)`;
        return (
          <div key={d} style={{background:bg, border:`1px solid ${bd}`, borderRadius:4, padding:'8px 6px', textAlign:'center'}}>
            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.1em'}}>{d.slice(5)}</div>
            <div className="mono" style={{fontSize:12,fontWeight:800,color:v>=0?'var(--green-soft)':'var(--red-2)',marginTop:2}}>{v>=0?'+':''}{v.toFixed(0)}</div>
          </div>
        );
      })}
    </div>
  );
}

function TradeTable({ trades, onSelect, sortKey, setSortKey, sortDir, setSortDir, query, setQuery }){
  const sorted = useMemo(()=>{
    let arr = trades.filter(t => !query || t.sym.toLowerCase().includes(query.toLowerCase()) || t.setup.toLowerCase().includes(query.toLowerCase()) || t.tags.join(' ').toLowerCase().includes(query.toLowerCase()));
    arr = [...arr].sort((a,b) => {
      const A = a[sortKey], B = b[sortKey];
      if (typeof A === 'number') return (B-A)*(sortDir==='asc'?-1:1);
      return String(A).localeCompare(String(B))*(sortDir==='asc'?1:-1);
    });
    return arr;
  }, [trades, query, sortKey, sortDir]);
  const headers = [
    { k:'date', l:'DATE' },
    { k:'sym',  l:'SYMBOL' },
    { k:'dir',  l:'DIR' },
    { k:'setup',l:'SETUP' },
    { k:'pnl',  l:'P&L' },
    { k:'rr',   l:'R' },
    { k:'mfe',  l:'MFE' },
    { k:'mae',  l:'MAE' },
    { k:'dur',  l:'DUR' },
  ];
  const onSort = (k) => {
    if (sortKey===k) setSortDir(sortDir==='asc'?'desc':'asc');
    else { setSortKey(k); setSortDir('desc'); }
  };
  return (
    <>
      <div style={{padding:'10px 18px',borderBottom:'1px solid var(--border-soft)',display:'flex',gap:8,alignItems:'center'}}>
        <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="// filter symbol, setup, tag..." style={{flex:1,background:'rgba(0,0,0,.4)',border:'1px solid var(--border-soft)',color:'var(--fg)',padding:'8px 12px',borderRadius:6,fontFamily:'JetBrains Mono,monospace',fontSize:11,letterSpacing:'.05em',outline:'none'}}/>
        <SS.Chip>{sorted.length} TRADES</SS.Chip>
      </div>
      <div style={{maxHeight:520,overflowY:'auto'}}>
        <div style={{display:'grid',gridTemplateColumns:'90px 1fr 50px 1fr 80px 50px 50px 50px 60px 1fr 70px',gap:8,padding:'10px 18px',fontFamily:'JetBrains Mono,monospace',fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',position:'sticky',top:0,background:'var(--card)',zIndex:1,borderBottom:'1px solid var(--border-soft)'}}>
          {headers.map(h => (
            <span key={h.k} onClick={()=>onSort(h.k)} style={{cursor:'pointer',color:sortKey===h.k?'var(--accent)':'var(--fg-4)'}}>
              {h.l}{sortKey===h.k?(sortDir==='asc'?' ↑':' ↓'):''}
            </span>
          ))}
          <span>TAGS</span>
          <span style={{textAlign:'right'}}>EXIT</span>
        </div>
        {sorted.map(tr => {
          const profit = tr.pnl>=0;
          return (
            <div key={tr.id} onClick={()=>onSelect(tr)} style={{display:'grid',gridTemplateColumns:'90px 1fr 50px 1fr 80px 50px 50px 50px 60px 1fr 70px',gap:8,padding:'10px 18px',borderBottom:'1px solid var(--border-soft)',cursor:'pointer',alignItems:'center',fontFamily:'JetBrains Mono,monospace',fontSize:11,transition:'background .15s'}} onMouseOver={e=>e.currentTarget.style.background='rgba(255,255,255,.03)'} onMouseOut={e=>e.currentTarget.style.background='transparent'}>
              <span style={{color:'var(--fg-3)'}}>{tr.date.slice(5)}</span>
              <span style={{color:'var(--fg)',fontWeight:600,letterSpacing:'.04em'}}>{tr.sym}</span>
              <span style={{color:tr.dir==='LONG'?'var(--green-soft)':'var(--red-2)',fontWeight:700}}>{tr.dir==='LONG'?'▲L':'▼S'}</span>
              <span style={{color:'var(--fg-2)',fontSize:10}}>{tr.setup}</span>
              <span style={{color:profit?'var(--green-soft)':'var(--red-2)',fontWeight:800}}>{(profit?'+':'')+SS.fmtMoney(tr.pnl)}</span>
              <span style={{color:tr.rr>=1?'var(--green-soft)':'var(--red-2)'}}>{tr.rr>=0?'+':''}{tr.rr.toFixed(1)}R</span>
              <span style={{color:'var(--green-soft)'}}>{tr.mfe.toFixed(2)}</span>
              <span style={{color:'var(--red-2)'}}>{tr.mae.toFixed(2)}</span>
              <span style={{color:'var(--fg-3)'}}>{tr.dur}m</span>
              <span style={{display:'flex',gap:3,flexWrap:'wrap'}}>
                {tr.tags.map(t=>(<span key={t} className="chip" style={{fontSize:8,padding:'1px 5px'}}>{t}</span>))}
              </span>
              <span style={{color:'var(--fg-4)',fontSize:9,textAlign:'right',letterSpacing:'.1em'}}>{tr.exit.replace(/_/g,' ').toUpperCase()}</span>
            </div>
          );
        })}
      </div>
    </>
  );
}

function TradeDetail({ trade, onClose, notes, setNotes }){
  if (!trade) return null;
  const profit = trade.pnl>=0;
  return (
    <SS.Modal onClose={onClose} maxWidth={680}>
      <div style={{padding:'14px 18px',borderBottom:'1px solid var(--border-soft)',background:'rgba(0,0,0,.4)',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <SS.Chip kind={trade.dir==='LONG'?'green':'red'}>{trade.dir==='LONG'?'▲':'▼'} {trade.dir}</SS.Chip>
          <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:18,letterSpacing:'.08em'}}>{trade.sym}</span>
          <SS.Chip>{trade.setup}</SS.Chip>
          <SS.Chip kind={profit?'green':'red'}>{profit?'+':''}{SS.fmtMoney(trade.pnl)} · {SS.fmtPct(trade.pnl_pct)}</SS.Chip>
        </div>
        <button className="btn" style={{padding:'6px 10px'}} onClick={onClose}>✕</button>
      </div>
      <div style={{padding:'14px 18px',display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
        <div>
          <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// EXECUTION</div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            <div className="metric-tile"><div className="metric-label">P&L</div><div className="metric-value" style={{color:profit?'var(--green-soft)':'var(--red-2)'}}>{(profit?'+':'')+SS.fmtMoney(trade.pnl)}</div></div>
            <div className="metric-tile"><div className="metric-label">R</div><div className="metric-value" style={{color:trade.rr>=1?'var(--green-soft)':'var(--red-2)'}}>{trade.rr>=0?'+':''}{trade.rr.toFixed(2)}R</div></div>
            <div className="metric-tile"><div className="metric-label">MFE</div><div className="metric-value" style={{color:'var(--green-soft)'}}>+{trade.mfe.toFixed(2)}%</div></div>
            <div className="metric-tile"><div className="metric-label">MAE</div><div className="metric-value" style={{color:'var(--red-2)'}}>-{trade.mae.toFixed(2)}%</div></div>
            <div className="metric-tile"><div className="metric-label">Duration</div><div className="metric-value">{trade.dur}m</div></div>
            <div className="metric-tile"><div className="metric-label">Confidence</div><div className="metric-value" style={{color:'var(--accent)'}}>{trade.conf}</div></div>
          </div>
        </div>
        <div>
          <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// EFFICIENCY</div>
          <div style={{padding:14,border:'1px solid var(--border-soft)',borderRadius:8,background:'rgba(0,0,0,.3)'}}>
            <div style={{position:'relative',height:14,background:'rgba(0,0,0,.4)',border:'1px solid var(--border-soft)',borderRadius:3,marginBottom:6}}>
              <div style={{position:'absolute',top:0,bottom:0,left:'50%',width:1,background:'rgba(255,255,255,.2)'}}/>
              <div style={{position:'absolute',top:0,bottom:0,left:'50%',width:Math.min(50,(trade.mfe/4)*50)+'%',background:'rgba(34,197,94,.55)',borderRadius:'0 2px 2px 0'}}/>
              <div style={{position:'absolute',top:0,bottom:0,right:'50%',width:Math.min(50,(trade.mae/4)*50)+'%',background:'rgba(248,113,113,.55)',borderRadius:'2px 0 0 2px'}}/>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',fontSize:10,fontFamily:'JetBrains Mono,monospace'}}>
              <span style={{color:'var(--red-2)'}}>MAE -{trade.mae.toFixed(2)}%</span>
              <span style={{color:'var(--fg-4)'}}>ENTRY</span>
              <span style={{color:'var(--green-soft)'}}>MFE +{trade.mfe.toFixed(2)}%</span>
            </div>
            <div style={{marginTop:14,fontSize:11,color:'var(--fg-3)',lineHeight:1.5}}>
              Captured <b style={{color:'var(--green-soft)'}}>{((trade.pnl_pct/trade.mfe)*100).toFixed(0)}%</b> of max favorable excursion.
              {trade.mae > Math.abs(trade.pnl_pct) && <> Stop sat through <b style={{color:'var(--red-2)'}}>{trade.mae.toFixed(2)}%</b> drawdown.</>}
            </div>
          </div>
          <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginTop:14,marginBottom:8}}>// TAGS</div>
          <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
            {trade.tags.map(tg => <SS.Chip key={tg}>{tg}</SS.Chip>)}
            {trade.tags.length===0 && <span style={{fontSize:11,color:'var(--fg-4)'}}>// no tags</span>}
            <SS.Chip kind="accent" style={{cursor:'pointer'}}>+ ADD</SS.Chip>
          </div>
        </div>
      </div>
      <div style={{padding:'14px 18px',borderTop:'1px solid var(--border-soft)'}}>
        <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// JOURNAL ENTRY</div>
        <textarea
          value={notes[trade.id]||''}
          onChange={e=>setNotes({...notes,[trade.id]:e.target.value})}
          placeholder="// what worked, what didn't, lesson..."
          style={{width:'100%',minHeight:80,background:'rgba(0,0,0,.4)',border:'1px solid var(--border-soft)',borderRadius:6,color:'var(--fg)',padding:10,fontFamily:'JetBrains Mono,monospace',fontSize:11,lineHeight:1.5,outline:'none',resize:'vertical'}}
        />
      </div>
    </SS.Modal>
  );
}

function App(){
  const [t, setTweak] = window.useTweaks({
    ...SS.SHARED_TWEAK_DEFAULTS,
    groupBy: 'setup',  // 'setup' | 'symbol'
    timeRange: '7d',
  });
  useEffect(()=>{ SS.applyTweaks(t, 'green'); }, [t]);

  const [now, setNow] = useState(Date.now());
  const [trades] = useState(TRADES_SEED);
  const [selected, setSelected] = useState(null);
  const [notes, setNotes] = useState({});
  const [sortKey, setSortKey] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const [query, setQuery] = useState('');

  useEffect(()=>{
    const id = setInterval(()=>setNow(Date.now()), 1000);
    return ()=>clearInterval(id);
  }, []);

  // Stats
  const wins = trades.filter(x=>x.pnl>0);
  const losses = trades.filter(x=>x.pnl<=0);
  const winRate = (wins.length/trades.length)*100;
  const totalPnl = trades.reduce((a,x)=>a+x.pnl,0);
  const avgWin = wins.length ? wins.reduce((a,x)=>a+x.pnl,0)/wins.length : 0;
  const avgLoss = losses.length ? Math.abs(losses.reduce((a,x)=>a+x.pnl,0))/losses.length : 0;
  const profitFactor = avgLoss>0 ? (avgWin*wins.length)/(avgLoss*losses.length) : Infinity;
  const expectancy = (winRate/100)*avgWin - (1-winRate/100)*avgLoss;
  const avgR = trades.reduce((a,x)=>a+x.rr,0)/trades.length;
  const avgMfe = trades.reduce((a,x)=>a+x.mfe,0)/trades.length;
  const avgMae = trades.reduce((a,x)=>a+x.mae,0)/trades.length;
  const avgDur = trades.reduce((a,x)=>a+x.dur,0)/trades.length;

  // Group breakdown
  const groups = useMemo(()=>{
    const map = {};
    trades.forEach(tr => {
      const k = tr[t.groupBy === 'symbol' ? 'sym' : 'setup'];
      if (!map[k]) map[k] = { k, n:0, wins:0, pnl:0, sumR:0 };
      map[k].n++; map[k].pnl += tr.pnl; map[k].sumR += tr.rr;
      if (tr.pnl>0) map[k].wins++;
    });
    return Object.values(map).sort((a,b)=>b.pnl-a.pnl);
  }, [trades, t.groupBy]);

  return (
    <div className="shell">
      <SS.Topbar active="journal" now={now}/>
      <SS.PageHead
        icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <rect x="4" y="3" width="14" height="18" rx="1.5" stroke="var(--green)" strokeWidth="1.7"/>
          <line x1="8" y1="7" x2="14" y2="7" stroke="var(--green)" strokeWidth="1.5"/>
          <line x1="8" y1="11" x2="14" y2="11" stroke="var(--green)" strokeWidth="1.5"/>
          <line x1="8" y1="15" x2="11" y2="15" stroke="var(--green)" strokeWidth="1.5"/>
          <circle cx="20" cy="20" r="3" stroke="var(--accent)" strokeWidth="1.4"/>
          <line x1="22" y1="22" x2="24" y2="24" stroke="var(--accent)" strokeWidth="1.4"/>
        </svg>}
        title="Journal"
        subtitle={`${trades.length} closed trades · ${t.timeRange} window`}
        badges={<>
          <SS.Chip kind={totalPnl>=0?'green':'red'}>NET {totalPnl>=0?'+':''}{SS.fmtMoney(totalPnl)}</SS.Chip>
          <SS.Chip kind="green">WR {winRate.toFixed(0)}%</SS.Chip>
          <SS.Chip kind="accent">PF {profitFactor.toFixed(2)}</SS.Chip>
        </>}
      />

      {/* Stats command center */}
      <section className="panel panel-accent" style={{marginBottom:18}}>
        <SS.Reticle/>
        <div className="corner-tag tl">// PERFORMANCE-METRICS</div>
        <div className="corner-tag tr">{t.timeRange.toUpperCase()} WINDOW</div>
        <div style={{padding:'22px 22px 18px'}}>
          <div style={{display:'grid',gridTemplateColumns:'repeat(8, minmax(0,1fr))',gap:10,marginBottom:18}}>
            <StatTile label="Net P&L"     value={(totalPnl>=0?'+':'')+SS.fmtMoney(totalPnl)} sub="across all closed" color={totalPnl>=0?'var(--green-soft)':'var(--red-2)'} big/>
            <StatTile label="Win Rate"    value={winRate.toFixed(1)+'%'} sub={wins.length+' / '+trades.length} color="var(--green-soft)" big/>
            <StatTile label="Profit Fctr" value={profitFactor.toFixed(2)} sub={profitFactor>1.5?'healthy':profitFactor>1?'thin':'losing'} color={profitFactor>1.5?'var(--green-soft)':profitFactor>1?'var(--amber)':'var(--red-2)'} big/>
            <StatTile label="Avg R"       value={(avgR>=0?'+':'')+avgR.toFixed(2)+'R'} sub="per trade" color={avgR>=0?'var(--green-soft)':'var(--red-2)'} big/>
            <StatTile label="Expectancy"  value={(expectancy>=0?'+':'')+SS.fmtMoney(expectancy)} sub="per trade EV" color={expectancy>=0?'var(--green-soft)':'var(--red-2)'} big/>
            <StatTile label="Avg Win"     value={'+'+SS.fmtMoney(avgWin)} sub={wins.length+' wins'} color="var(--green-soft)"/>
            <StatTile label="Avg Loss"    value={'-'+SS.fmtMoney(avgLoss)} sub={losses.length+' losses'} color="var(--red-2)"/>
            <StatTile label="Avg Duration"value={avgDur.toFixed(0)+'m'} sub={'MFE '+avgMfe.toFixed(2)+'% / MAE '+avgMae.toFixed(2)+'%'} color="var(--fg)"/>
          </div>

          <div style={{paddingTop:14,borderTop:'1px solid var(--border-soft)'}}>
            <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.20em',textTransform:'uppercase',marginBottom:10}}>// EQUITY · DRAWDOWN</div>
            <EquityCurve trades={trades} initial={5000}/>
          </div>
        </div>
      </section>

      <div className="layout-grid">
        {/* Trades table */}
        <div className="col">
          <section className="panel">
            <SS.SectionHead title="Trade Log" right={<>
              <SS.Chip kind="accent">SORT · {sortKey.toUpperCase()} {sortDir==='desc'?'↓':'↑'}</SS.Chip>
            </>}/>
            <TradeTable
              trades={trades}
              onSelect={setSelected}
              sortKey={sortKey} setSortKey={setSortKey}
              sortDir={sortDir} setSortDir={setSortDir}
              query={query} setQuery={setQuery}
            />
          </section>

          <section className="panel">
            <SS.SectionHead title="P&L Calendar" right={<SS.Chip>DAILY</SS.Chip>}/>
            <div style={{padding:'14px 18px'}}>
              <PnLCalendar trades={trades}/>
            </div>
          </section>
        </div>

        {/* Right rail */}
        <div className="col">
          <section className="panel">
            <SS.SectionHead title={`Per-${t.groupBy === 'symbol' ? 'Symbol' : 'Setup'} Breakdown`} right={
              <div style={{display:'flex',gap:6}}>
                <button className={`btn ${t.groupBy==='setup'?'btn-cyan':''}`} style={{padding:'4px 10px',fontSize:10}} onClick={()=>setTweak('groupBy','setup')}>SETUP</button>
                <button className={`btn ${t.groupBy==='symbol'?'btn-cyan':''}`} style={{padding:'4px 10px',fontSize:10}} onClick={()=>setTweak('groupBy','symbol')}>SYMBOL</button>
              </div>
            }/>
            <div style={{padding:'14px 18px',display:'flex',flexDirection:'column',gap:10}}>
              {groups.map(g => {
                const wr = (g.wins/g.n)*100;
                const profit = g.pnl>=0;
                const max = Math.max(...groups.map(x=>Math.abs(x.pnl)));
                const w = (Math.abs(g.pnl)/max)*100;
                return (
                  <div key={g.k} style={{padding:'10px 12px',border:'1px solid var(--border-soft)',borderRadius:8,background:'rgba(0,0,0,.3)',position:'relative',overflow:'hidden'}}>
                    <div style={{position:'absolute',top:0,bottom:0,left:0,width:w+'%',background:profit?'rgba(34,197,94,.05)':'rgba(248,113,113,.05)',borderRight:`1px solid ${profit?'rgba(34,197,94,.3)':'rgba(248,113,113,.3)'}`}}/>
                    <div style={{position:'relative',display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                      <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:13,letterSpacing:'.06em'}}>{g.k}</span>
                      <span className="mono" style={{fontSize:13,fontWeight:800,color:profit?'var(--green-soft)':'var(--red-2)'}}>{(profit?'+':'')+SS.fmtMoney(g.pnl)}</span>
                    </div>
                    <div style={{position:'relative',display:'flex',justifyContent:'space-between',fontSize:10,fontFamily:'JetBrains Mono,monospace',color:'var(--fg-4)',letterSpacing:'.14em'}}>
                      <span>{g.n} TRADES</span>
                      <span style={{color:wr>=60?'var(--green-soft)':wr>=40?'var(--amber)':'var(--red-2)'}}>WR {wr.toFixed(0)}%</span>
                      <span>AVG {(g.sumR/g.n).toFixed(2)}R</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="panel">
            <SS.SectionHead title="Tag Cloud" right={<SS.Chip>{Object.keys([...trades].reduce((a,t)=>{t.tags.forEach(tg=>a[tg]=true);return a;},{})).length} TAGS</SS.Chip>}/>
            <div style={{padding:'14px 18px'}}>
              <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
                {Object.entries(trades.reduce((a,t)=>{t.tags.forEach(tg=>a[tg]=(a[tg]||{count:0,pnl:0}, {count:(a[tg]?.count||0)+1, pnl:(a[tg]?.pnl||0)+t.pnl}));return a;},{})).sort((a,b)=>b[1].count-a[1].count).map(([tag,d])=>(
                  <div key={tag} style={{padding:'8px 12px',border:`1px solid ${d.pnl>=0?'rgba(34,197,94,.4)':'rgba(248,113,113,.4)'}`,borderRadius:6,background:d.pnl>=0?'rgba(34,197,94,.08)':'rgba(248,113,113,.08)',display:'flex',flexDirection:'column',gap:2}}>
                    <span className="mono" style={{fontSize:11,color:'var(--fg)',fontWeight:700,letterSpacing:'.05em'}}>{tag}</span>
                    <span className="mono" style={{fontSize:9,color:'var(--fg-4)'}}>{d.count} · <span style={{color:d.pnl>=0?'var(--green-soft)':'var(--red-2)'}}>{(d.pnl>=0?'+':'')+SS.fmtMoney(d.pnl)}</span></span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="panel">
            <SS.SectionHead title="Distribution" right={<SS.Chip kind="accent">EFFICIENCY</SS.Chip>}/>
            <div style={{padding:'14px 18px'}}>
              <svg viewBox="0 0 320 140" style={{width:'100%'}}>
                {/* grid */}
                <line x1="20" y1="120" x2="310" y2="120" stroke="rgba(255,255,255,.1)"/>
                <line x1="165" y1="20" x2="165" y2="120" stroke="rgba(255,255,255,.06)" strokeDasharray="2 3"/>
                <text x="20" y="135" fill="var(--fg-4)" fontSize="8" fontFamily="JetBrains Mono,monospace">-2R</text>
                <text x="159" y="135" fill="var(--fg-4)" fontSize="8" fontFamily="JetBrains Mono,monospace">0</text>
                <text x="298" y="135" fill="var(--fg-4)" fontSize="8" fontFamily="JetBrains Mono,monospace">+3R</text>
                {/* trades as dots */}
                {trades.map((tr,i) => {
                  const x = 165 + (tr.rr/3)*145;
                  const y = 110 - (tr.mfe/4)*85;
                  const c = tr.pnl>=0?'#22c55e':'#f87171';
                  return <circle key={i} cx={x} cy={y} r="3.5" fill={c} fillOpacity=".7" stroke={c}/>;
                })}
                <text x="20" y="18" fill="var(--fg-4)" fontSize="9" fontFamily="JetBrains Mono,monospace" letterSpacing=".18em">MFE % ↑ vs R →</text>
              </svg>
            </div>
          </section>
        </div>
      </div>

      <SS.FooterStatus now={now} latency={36}/>

      {selected && <TradeDetail trade={selected} onClose={()=>setSelected(null)} notes={notes} setNotes={setNotes}/>}

      <window.TweaksPanel title="Tweaks" defaultOpen={false}>
        <SS.SharedTweaksControls t={t} setTweak={setTweak}/>
        <window.TweakSection title="Journal">
          <window.TweakRadio label="Time Range" value={t.timeRange} onChange={v=>setTweak('timeRange',v)} options={[
            {label:'24h',value:'24h'},
            {label:'7d', value:'7d'},
            {label:'30d',value:'30d'},
            {label:'All',value:'all'},
          ]}/>
          <window.TweakRadio label="Group By" value={t.groupBy} onChange={v=>setTweak('groupBy',v)} options={[
            {label:'Setup', value:'setup'},
            {label:'Symbol',value:'symbol'},
          ]}/>
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

// ── SCANNER — Live signal grid + radar + console ────────────
const SS = window.SS;

const SETUPS = ['OB+FVG','BOS','CHoCH','LIQ-SWEEP','OB-RETEST','FVG-FILL','BREAKER'];
const TFS = ['1m','5m','15m','1h','4h','1D'];
const REGIMES = ['TREND','RANGE','CHOP'];

const SIGNAL_SEED = [
  { id:'s1', sym:'BTC/USDT', dir:'LONG',  setup:'OB+FVG',    score:8.2, tf:'1h',  conf:'HIGH', regime:'TREND', mark:65120.25, entry:64580, sl:63450, tp1:65800, tp2:66600, rr:2.1, age:42, bias:[8,9,7,8] },
  { id:'s2', sym:'ETH/USDT', dir:'LONG',  setup:'BOS',       score:7.4, tf:'15m', conf:'HIGH', regime:'TREND', mark:3198.40,  entry:3180,  sl:3142, tp1:3260,  tp2:3305,  rr:1.8, age:18, bias:[7,8,7,7] },
  { id:'s3', sym:'SOL/USDT', dir:'SHORT', setup:'LIQ-SWEEP', score:7.8, tf:'15m', conf:'HIGH', regime:'RANGE', mark:141.05,   entry:142.4, sl:145.4,tp1:139.4, tp2:137.8, rr:1.9, age:11, bias:[8,7,8,8] },
  { id:'s4', sym:'TON/USDT', dir:'LONG',  setup:'OB-RETEST', score:6.9, tf:'1h',  conf:'MED',  regime:'TREND', mark:6.842,    entry:6.78,  sl:6.62, tp1:6.95,  tp2:7.12,  rr:1.6, age:55, bias:[7,7,6,7] },
  { id:'s5', sym:'INJ/USDT', dir:'LONG',  setup:'FVG-FILL',  score:6.4, tf:'5m',  conf:'MED',  regime:'TREND', mark:24.18,    entry:24.04, sl:23.62,tp1:24.55, tp2:24.85, rr:1.4, age:7,  bias:[6,7,6,6] },
  { id:'s6', sym:'AAVE/USDT',dir:'SHORT', setup:'CHoCH',     score:6.1, tf:'1h',  conf:'MED',  regime:'RANGE', mark:92.18,    entry:93.0,  sl:95.4, tp1:90.2,  tp2:88.4,  rr:1.5, age:33, bias:[6,5,7,6] },
  { id:'s7', sym:'OP/USDT',  dir:'SHORT', setup:'BREAKER',   score:5.8, tf:'15m', conf:'LOW',  regime:'RANGE', mark:1.892,    entry:1.910, sl:1.95, tp1:1.85,  tp2:1.81,  rr:1.4, age:22, bias:[5,6,6,5] },
  { id:'s8', sym:'NEAR/USDT',dir:'LONG',  setup:'OB+FVG',    score:5.2, tf:'5m',  conf:'LOW',  regime:'CHOP',  mark:4.310,    entry:4.28,  sl:4.18, tp1:4.39,  tp2:4.46,  rr:1.3, age:14, bias:[5,5,5,5] },
];

function MiniChart({ sig }){
  const N = 30;
  const candles = useMemo(()=>{
    const arr = [];
    let p = sig.entry * (sig.dir==='LONG'? 0.99 : 1.01);
    for (let i=0;i<N;i++){
      const drift = (sig.dir==='LONG'?0.0008:-0.0008);
      const vol = (Math.sin(i*1.7+sig.id.charCodeAt(1))*0.005);
      const open = p, close = p*(1+drift+vol);
      arr.push({open,close,hi:Math.max(open,close)*1.003,lo:Math.min(open,close)*0.997});
      p = close;
    }
    const f = sig.mark / arr[arr.length-1].close;
    arr.forEach(c=>{c.open*=f;c.close*=f;c.hi*=f;c.lo*=f;});
    return arr;
  }, [sig]);
  const allP = [...candles.flatMap(c=>[c.hi,c.lo]), sig.entry, sig.sl, sig.tp1];
  const yMin = Math.min(...allP)*.998, yMax=Math.max(...allP)*1.002, yR=yMax-yMin;
  const W=240, H=70, pad=3;
  const cw = (W-2*pad)/candles.length;
  const yOf = p => pad + ((yMax-p)/yR)*(H-2*pad);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{width:'100%',height:70,background:'rgba(0,0,0,.35)',borderRadius:4}}>
      <line x1={pad} x2={W-pad} y1={yOf(sig.entry)} y2={yOf(sig.entry)} stroke="#60a5fa" strokeWidth=".5" strokeDasharray="2 3" opacity=".7"/>
      <line x1={pad} x2={W-pad} y1={yOf(sig.sl)}    y2={yOf(sig.sl)}    stroke="#f87171" strokeWidth=".5" strokeDasharray="2 3" opacity=".7"/>
      <line x1={pad} x2={W-pad} y1={yOf(sig.tp1)}   y2={yOf(sig.tp1)}   stroke="#22c55e" strokeWidth=".5" strokeDasharray="2 3" opacity=".7"/>
      {candles.map((c,i)=>{
        const x=pad+i*cw+cw*0.15, w=cw*0.7;
        const yO=yOf(c.open), yC=yOf(c.close), yH=yOf(c.hi), yL=yOf(c.lo);
        const up = c.close>=c.open, color = up?'#22c55e':'#f87171';
        return <g key={i}>
          <line x1={x+w/2} x2={x+w/2} y1={yH} y2={yL} stroke={color} strokeWidth=".5" opacity=".6"/>
          <rect x={x} y={Math.min(yO,yC)} width={w} height={Math.max(.8,Math.abs(yC-yO))} fill={color} opacity=".85"/>
        </g>;
      })}
      <circle cx={W-pad-2} cy={yOf(sig.mark)} r="2" fill="#fbbf24"/>
    </svg>
  );
}

function SignalCard({ sig, onSelect, selected }){
  const isLong = sig.dir==='LONG';
  const confCol = sig.conf==='HIGH'?'var(--green-soft)':sig.conf==='MED'?'var(--amber)':'var(--fg-3)';
  const setupCol = sig.setup.includes('FVG')?'cyan':sig.setup.includes('BOS')||sig.setup.includes('CHoCH')?'purple':sig.setup.includes('LIQ')?'amber':'';
  return (
    <div className={`pos brackets ${selected?'flash-green':''}`} style={{cursor:'pointer'}} onClick={()=>onSelect(sig)}>
      <div className="corner-tag tl">// {sig.id.toUpperCase()}</div>
      <div className="corner-tag tr">{sig.tf} · {sig.age}m AGO</div>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:10,marginTop:4,flexWrap:'wrap'}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <SS.Chip kind={isLong?'green':'red'}>{isLong?'▲':'▼'} {sig.dir}</SS.Chip>
          <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:16,letterSpacing:'.06em'}}>{sig.sym}</span>
          <SS.Chip kind={setupCol} style={{fontSize:9}}>{sig.setup}</SS.Chip>
        </div>
        <div style={{textAlign:'right'}}>
          <div className="mono" style={{fontSize:18,fontWeight:800,color:confCol,lineHeight:1}}>{sig.score.toFixed(1)}</div>
          <div className="mono" style={{fontSize:8,color:confCol,letterSpacing:'.18em'}}>{sig.conf}</div>
        </div>
      </div>
      <MiniChart sig={sig}/>
      <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:'8px 10px',marginTop:10}}>
        <SS.Mini label="Entry" value={SS.fmtPrice(sig.entry)}/>
        <SS.Mini label="Stop"  value={SS.fmtPrice(sig.sl)} valueColor="var(--red-2)"/>
        <SS.Mini label="TP1"   value={SS.fmtPrice(sig.tp1)} valueColor="var(--green-soft)"/>
        <SS.Mini label="R:R"   value={sig.rr.toFixed(1)+':1'} accent/>
      </div>
      <div style={{display:'flex',gap:6,marginTop:10}}>
        <SS.Chip kind={sig.regime==='TREND'?'green':sig.regime==='RANGE'?'amber':'red'} style={{fontSize:9}}>{sig.regime}</SS.Chip>
        {sig.bias[0]>=7 && <SS.Chip style={{fontSize:9}}>HTF ✓</SS.Chip>}
        {sig.bias[1]>=7 && <SS.Chip style={{fontSize:9}}>VOL ✓</SS.Chip>}
        <span style={{flex:1}}/>
        <button className="btn btn-green" style={{padding:'4px 10px',fontSize:10}} onClick={e=>{e.stopPropagation();}}>▶ TAKE</button>
      </div>
    </div>
  );
}

function FilterRail({ filters, setFilters, counts }){
  const F = filters;
  const upd = (k,v) => setFilters({...F, [k]:v});
  const toggleSet = (k, v) => {
    const set = new Set(F[k]);
    if (set.has(v)) set.delete(v); else set.add(v);
    upd(k, [...set]);
  };
  return (
    <div style={{padding:'14px 16px',display:'flex',flexDirection:'column',gap:14}}>
      <div>
        <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// MIN SCORE · {F.minScore.toFixed(1)}</div>
        <input type="range" min="0" max="10" step=".1" value={F.minScore} onChange={e=>upd('minScore',+e.target.value)} style={{width:'100%'}}/>
        <div style={{display:'flex',justifyContent:'space-between',marginTop:4}}>
          <span className="mono" style={{fontSize:9,color:'var(--fg-4)'}}>0.0</span>
          <span className="mono" style={{fontSize:9,color:'var(--accent)'}}>≥ {F.minScore.toFixed(1)}</span>
          <span className="mono" style={{fontSize:9,color:'var(--fg-4)'}}>10.0</span>
        </div>
      </div>
      <div>
        <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// DIRECTION</div>
        <div style={{display:'flex',gap:6}}>
          {['ALL','LONG','SHORT'].map(d => (
            <button key={d} className={`btn ${F.dir===d?(d==='LONG'?'btn-green':d==='SHORT'?'btn-red':'btn-cyan'):''}`} style={{padding:'6px 10px',fontSize:10,flex:1}} onClick={()=>upd('dir',d)}>{d}</button>
          ))}
        </div>
      </div>
      <div>
        <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// TIMEFRAME</div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:6}}>
          {TFS.map(tf => {
            const active = F.tfs.includes(tf);
            return <button key={tf} className={`btn ${active?'btn-cyan':''}`} style={{padding:'6px 10px',fontSize:10}} onClick={()=>toggleSet('tfs',tf)}>{tf}</button>;
          })}
        </div>
      </div>
      <div>
        <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// SETUP</div>
        <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
          {SETUPS.map(s => {
            const active = F.setups.includes(s);
            return <button key={s} className={`btn ${active?'btn-cyan':''}`} style={{padding:'5px 9px',fontSize:9}} onClick={()=>toggleSet('setups',s)}>{s}</button>;
          })}
        </div>
      </div>
      <div>
        <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// REGIME</div>
        <div style={{display:'flex',gap:6}}>
          {REGIMES.map(r => {
            const active = F.regimes.includes(r);
            const kind = r==='TREND'?'btn-green':r==='RANGE'?'btn-cyan':'btn-red';
            return <button key={r} className={`btn ${active?kind:''}`} style={{padding:'6px 10px',fontSize:10,flex:1}} onClick={()=>toggleSet('regimes',r)}>{r}</button>;
          })}
        </div>
      </div>
      <div style={{paddingTop:12,borderTop:'1px solid var(--border-soft)',display:'flex',flexDirection:'column',gap:8}}>
        <div style={{display:'flex',justifyContent:'space-between'}}>
          <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>passing</span>
          <span className="mono" style={{fontSize:11,color:'var(--accent)',fontWeight:700}}>{counts.passing} / {counts.total}</span>
        </div>
        <button className="btn" style={{padding:'8px',fontSize:10}} onClick={()=>setFilters({minScore:0, dir:'ALL', tfs:[...TFS], setups:[...SETUPS], regimes:[...REGIMES]})}>RESET FILTERS</button>
      </div>
    </div>
  );
}

function SignalDetail({ sig, onClose, onTake }){
  if (!sig) return null;
  const isLong = sig.dir==='LONG';
  const N = 60;
  const candles = useMemo(()=>{
    const arr=[]; let p = sig.entry*(isLong?0.985:1.015);
    for (let i=0;i<N;i++){
      const drift = isLong?0.0012:-0.0012;
      const vol = (Math.sin(i*0.7+sig.id.charCodeAt(1))*0.004) + (Math.random()-.5)*0.005;
      const open=p, close=p*(1+drift+vol);
      arr.push({open,close,hi:Math.max(open,close)*1.003,lo:Math.min(open,close)*0.997});
      p=close;
    }
    const f = sig.mark / arr[arr.length-1].close;
    arr.forEach(c=>{c.open*=f;c.close*=f;c.hi*=f;c.lo*=f;});
    return arr;
  },[sig]);
  const levels = [
    { l:'TP2',   p: sig.tp2,   c:'#86efac' },
    { l:'TP1',   p: sig.tp1,   c:'#22c55e' },
    { l:'MARK',  p: sig.mark,  c:'#fbbf24' },
    { l:'ENTRY', p: sig.entry, c:'#60a5fa' },
    { l:'STOP',  p: sig.sl,    c:'#f87171' },
  ];
  const allP = [...candles.flatMap(c=>[c.hi,c.lo]), ...levels.map(l=>l.p)];
  const yMin=Math.min(...allP)*.997, yMax=Math.max(...allP)*1.003, yR=yMax-yMin;
  const W=560, H=300, lp=10, rp=70, tp=14, bp=14;
  const inW = W-lp-rp, inH = H-tp-bp;
  const cw = inW/candles.length;
  const yOf = p => tp + ((yMax-p)/yR)*inH;

  return (
    <SS.Modal onClose={onClose} maxWidth={680}>
      <div style={{padding:'14px 18px',borderBottom:'1px solid var(--border-soft)',background:'rgba(0,0,0,.4)',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <SS.Chip kind={isLong?'green':'red'}>{isLong?'▲':'▼'} {sig.dir}</SS.Chip>
          <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:18,letterSpacing:'.08em'}}>{sig.sym}</span>
          <SS.Chip>{sig.setup}</SS.Chip>
          <SS.Chip kind="amber">{sig.tf}</SS.Chip>
          <SS.Chip kind={sig.conf==='HIGH'?'green':'amber'}>{sig.conf} · {sig.score.toFixed(1)}</SS.Chip>
        </div>
        <button className="btn" style={{padding:'6px 10px'}} onClick={onClose}>✕</button>
      </div>
      <div style={{padding:'14px 18px'}}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{width:'100%',height:'auto',background:'rgba(0,0,0,.35)',border:'1px solid var(--border-soft)',borderRadius:8}}>
          {[0,.25,.5,.75,1].map(g=><line key={g} x1={lp} x2={W-rp} y1={tp+g*inH} y2={tp+g*inH} stroke="rgba(255,255,255,.05)" strokeDasharray="2 3"/>)}
          {/* OB / FVG zone shading */}
          <rect x={lp} y={yOf(sig.entry*1.003)} width={inW} height={Math.abs(yOf(sig.entry*1.003)-yOf(sig.entry*0.997))} fill="rgba(96,165,250,.12)" stroke="rgba(96,165,250,.3)" strokeDasharray="3 3"/>
          {candles.map((c,i)=>{
            const x = lp+i*cw+cw*0.15, w=cw*0.7;
            const yO=yOf(c.open), yC=yOf(c.close), yH=yOf(c.hi), yL=yOf(c.lo);
            const up = c.close>=c.open, color = up?'#22c55e':'#f87171';
            return <g key={i}>
              <line x1={x+w/2} x2={x+w/2} y1={yH} y2={yL} stroke={color} strokeWidth=".7" opacity=".7"/>
              <rect x={x} y={Math.min(yO,yC)} width={w} height={Math.max(1,Math.abs(yC-yO))} fill={color} opacity=".88"/>
            </g>;
          })}
          {levels.map((lv,i)=>{
            const y = yOf(lv.p);
            return <g key={i}>
              <line x1={lp} x2={W-rp} y1={y} y2={y} stroke={lv.c} strokeWidth=".7" strokeDasharray="3 3" opacity=".75"/>
              <rect x={W-rp+2} y={y-9} width={66} height={18} fill={lv.c} opacity=".18" stroke={lv.c} strokeOpacity=".55"/>
              <text x={W-rp+6} y={y+4} fill={lv.c} fontSize="9" fontWeight="700" fontFamily="JetBrains Mono,monospace" letterSpacing=".15em">{lv.l}</text>
              <text x={W-2} y={y+4} fill={lv.c} fontSize="9" fontWeight="700" fontFamily="JetBrains Mono,monospace" textAnchor="end">{lv.p<1?lv.p.toFixed(5):lv.p<100?lv.p.toFixed(3):lv.p.toFixed(2)}</text>
            </g>;
          })}
        </svg>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14,marginTop:14}}>
          <div>
            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// CONFLUENCE BREAKDOWN</div>
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              {[
                {k:'HTF Bias',     v:sig.bias[0]},
                {k:'Volume / OFI', v:sig.bias[1]},
                {k:'Setup Quality',v:sig.bias[2]},
                {k:'Regime Match', v:sig.bias[3]},
              ].map(x => (
                <div key={x.k} style={{display:'flex',alignItems:'center',gap:8}}>
                  <span className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.14em',width:110}}>{x.k}</span>
                  <div style={{flex:1,height:6,background:'rgba(0,0,0,.5)',borderRadius:3,border:'1px solid var(--border-soft)',overflow:'hidden'}}>
                    <div style={{height:'100%',width:(x.v*10)+'%',background:x.v>=7?'var(--green-soft)':x.v>=5?'var(--amber)':'var(--red-2)',boxShadow:`0 0 8px ${x.v>=7?'var(--green-soft)':'var(--amber)'}`}}/>
                  </div>
                  <span className="mono" style={{fontSize:11,fontWeight:700,color:'var(--fg)',width:24,textAlign:'right'}}>{x.v}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// EXECUTION SPEC</div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              <div className="metric-tile"><div className="metric-label">Risk</div><div className="metric-value">1.5%</div></div>
              <div className="metric-tile"><div className="metric-label">Lev</div><div className="metric-value">5×</div></div>
              <div className="metric-tile"><div className="metric-label">R:R</div><div className="metric-value" style={{color:'var(--accent)'}}>{sig.rr.toFixed(1)}:1</div></div>
              <div className="metric-tile"><div className="metric-label">Size</div><div className="metric-value">$1.2K</div></div>
            </div>
          </div>
        </div>
        <div style={{display:'flex',gap:10,marginTop:16,paddingTop:14,borderTop:'1px solid var(--border-soft)'}}>
          <button className="btn" onClick={onClose} style={{flex:1}}>DISMISS</button>
          <button className="btn btn-cyan" style={{flex:1}}>⌘ STAGE</button>
          <button className="btn btn-green" onClick={()=>onTake(sig)} style={{flex:2}}>▶ EXECUTE TRADE</button>
        </div>
      </div>
    </SS.Modal>
  );
}

function ScannerRadar({ signals }){
  return (
    <div className="radar-wrap">
      <svg viewBox="-100 -100 200 200" style={{width:'100%',height:'100%'}}>
        <defs>
          <linearGradient id="sweep2" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0"/>
            <stop offset="100%" stopColor="var(--accent)" stopOpacity=".5"/>
          </linearGradient>
        </defs>
        {[30,55,80].map(r=><circle key={r} r={r} fill="none" stroke="var(--accent)" strokeOpacity=".18" strokeWidth=".4"/>)}
        <line x1="-90" y1="0" x2="90" y2="0" stroke="var(--accent)" strokeOpacity=".15" strokeWidth=".4"/>
        <line x1="0" y1="-90" x2="0" y2="90" stroke="var(--accent)" strokeOpacity=".15" strokeWidth=".4"/>
        <g className="radar-sweep">
          <path d="M 0 0 L 88 0 A 88 88 0 0 0 67 -57 Z" fill="url(#sweep2)"/>
          <line x1="0" y1="0" x2="88" y2="0" stroke="var(--accent)" strokeOpacity=".55" strokeWidth=".6"/>
        </g>
        {signals.slice(0,12).map((s,i)=>{
          const angle = (i/12)*Math.PI*2 - Math.PI/2;
          const dist = 30 + (10-s.score)*5;
          const x = Math.cos(angle)*dist, y = Math.sin(angle)*dist;
          const armed = s.score>=7;
          const color = s.dir==='LONG'?'var(--green)':'var(--red-2)';
          return (
            <g key={s.id}>
              <circle cx={x} cy={y} r={armed?2.6:1.6} fill={color}>
                {armed && <animate attributeName="opacity" values="1;.3;1" dur="2s" repeatCount="indefinite"/>}
              </circle>
              {armed && <circle cx={x} cy={y} r="6" fill="none" stroke={color} strokeOpacity=".4"><animate attributeName="r" values="3;9" dur="2s" repeatCount="indefinite"/><animate attributeName="opacity" values=".7;0" dur="2s" repeatCount="indefinite"/></circle>}
              <text x={x+5} y={y-3} fontFamily="JetBrains Mono,monospace" fontSize="6" fill={color} fontWeight="700">{s.sym.split('/')[0]}</text>
            </g>
          );
        })}
        <circle r="3" fill="var(--accent)"/>
      </svg>
    </div>
  );
}

function App(){
  const [t, setTweak] = window.useTweaks({
    ...SS.SHARED_TWEAK_DEFAULTS,
    showRadar: true,
    autoExecute: false,
  });
  useEffect(()=>{ SS.applyTweaks(t, 'amber'); }, [t]);

  const [now, setNow] = useState(Date.now());
  const [signals, setSignals] = useState(SIGNAL_SEED);
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState({ minScore:0, dir:'ALL', tfs:[...TFS], setups:[...SETUPS], regimes:[...REGIMES] });
  const [logs, setLogs] = useState([
    { t:'14:42:18', sym:'BTC/USDT', passed:true,  reason:'OB+FVG aligned · BOS confirmed', conf:8.2 },
    { t:'14:41:55', sym:'ETH/USDT', passed:true,  reason:'4H OB · sweep + displacement',   conf:7.4 },
    { t:'14:41:32', sym:'SOL/USDT', passed:true,  reason:'liquidity sweep · CHoCH 15m',    conf:7.8 },
    { t:'14:41:09', sym:'AVAX/USDT',passed:false, reason:'HTF misaligned · regime CHOP',   conf:5.1 },
    { t:'14:40:46', sym:'TIA/USDT', passed:false, reason:'displacement < 1.5 ATR',         conf:4.6 },
    { t:'14:40:23', sym:'AAVE/USDT',passed:false, reason:'no fresh OB in last 50 candles', conf:3.9 },
  ]);
  const [scanProg, setScanProg] = useState({ done:18, total:25, current:'INJ/USDT' });

  useEffect(()=>{
    const id = setInterval(()=>{
      setNow(Date.now());
      setSignals(prev => prev.map(s => ({ ...s, mark: s.mark*(1+(Math.random()-0.5)*0.0008) })));
      setScanProg(p => ({ ...p, done: p.done>=p.total ? 1 : p.done+1, current: SIGNAL_SEED[(p.done+1)%SIGNAL_SEED.length].sym }));
      // occasional new log
      if (Math.random()<.3){
        const sigSym = ['BTC','ETH','SOL','AVAX','LINK','TIA','OP','ARB','AAVE'][Math.floor(Math.random()*9)]+'/USDT';
        const passed = Math.random()<.25;
        const time = new Date();
        const tt = `${String(time.getHours()).padStart(2,'0')}:${String(time.getMinutes()).padStart(2,'0')}:${String(time.getSeconds()).padStart(2,'0')}`;
        const reasons = passed? ['OB+FVG aligned · BOS','sweep + displacement','HTF + LTF aligned'] : ['HTF misaligned','volume gate failed','BTC veto active','spread > limit'];
        setLogs(prev => [{ t:tt, sym:sigSym, passed, reason:reasons[Math.floor(Math.random()*reasons.length)], conf: passed?+(7+Math.random()*1.5).toFixed(1):+(2+Math.random()*4).toFixed(1) }, ...prev].slice(0,16));
      }
    }, 2000/(t.simSpeed||1));
    return ()=>clearInterval(id);
  }, [t.simSpeed]);

  const filtered = useMemo(() => signals.filter(s => {
    if (s.score < filters.minScore) return false;
    if (filters.dir !== 'ALL' && s.dir !== filters.dir) return false;
    if (!filters.tfs.includes(s.tf)) return false;
    if (!filters.setups.includes(s.setup)) return false;
    if (!filters.regimes.includes(s.regime)) return false;
    return true;
  }), [signals, filters]);

  const armedCount = filtered.filter(s=>s.score>=7).length;

  return (
    <div className="shell">
      <SS.Topbar active="scanner" now={now}/>
      <SS.PageHead
        icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="var(--amber-2)" strokeWidth="1.7"/>
          <path d="M12 12 L20 6" stroke="var(--amber-2)" strokeWidth="1.7" strokeLinecap="round"/>
          <circle cx="12" cy="12" r="3" stroke="var(--amber-2)" strokeWidth="1.2"/>
          <path d="M12 4 L12 6 M12 18 L12 20 M4 12 L6 12 M18 12 L20 12" stroke="var(--amber-2)" strokeWidth="1.2"/>
        </svg>}
        title="Scanner"
        subtitle="real-time signal detection · 184 symbols · 6 timeframes"
        badges={<>
          <SS.Chip kind="amber">● SCANNING</SS.Chip>
          <SS.Chip kind="green">{armedCount} ARMED</SS.Chip>
          <SS.Chip>{scanProg.done}/{scanProg.total}</SS.Chip>
        </>}
      />

      {/* Top Command */}
      <section className="panel panel-accent" style={{marginBottom:18}}>
        <SS.Reticle/>
        <div className="corner-tag tl">// SCAN-CONTROL</div>
        <div className="corner-tag tr">PHANTOM ENGINE</div>
        <div style={{padding:'18px 22px'}}>
          <div style={{display:'grid',gridTemplateColumns:'2fr 1fr 1fr 1fr',gap:14,alignItems:'center'}}>
            <div>
              <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:4}}>// SCANNING</div>
              <div style={{display:'flex',alignItems:'center',gap:10}}>
                <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:22,letterSpacing:'.06em',color:'var(--accent)'}}>{scanProg.current}</span>
                <span className="cursor-blink" style={{color:'var(--accent)'}}>_</span>
              </div>
              <div style={{position:'relative',height:4,marginTop:8,borderRadius:2,background:'rgba(0,0,0,.5)',overflow:'hidden'}}>
                <div style={{position:'absolute',inset:0,width:((scanProg.done/scanProg.total)*100)+'%',background:'linear-gradient(90deg, rgba(251,191,36,.7), rgba(251,191,36,1))',boxShadow:'0 0 12px rgba(251,191,36,.5)',transition:'width .8s ease'}}/>
              </div>
            </div>
            <div className="metric-tile"><div className="metric-label">SIGNALS</div><div className="metric-value hud-glow-amber">{filtered.length}</div><div className="metric-sub">{armedCount} actionable</div></div>
            <div className="metric-tile"><div className="metric-label">SCAN INTERVAL</div><div className="metric-value">5m</div><div className="metric-sub">next sweep 47s</div></div>
            <div className="metric-tile"><div className="metric-label">MIN SCORE</div><div className="metric-value">≥ 7.0</div><div className="metric-sub">strict gate</div></div>
          </div>
        </div>
      </section>

      {/* Main 3-col */}
      <div className="layout-grid" style={{gridTemplateColumns:'260px 1fr 320px'}}>
        {/* Left rail */}
        <section className="panel" style={{position:'sticky',top:14,alignSelf:'start'}}>
          <SS.SectionHead title="Filters"/>
          <FilterRail filters={filters} setFilters={setFilters} counts={{passing:filtered.length, total:signals.length}}/>
        </section>

        {/* Center grid */}
        <section className="panel">
          <SS.SectionHead title={`Live Signals · ${filtered.length}`} right={<>
            <SS.Chip kind="green">SORT · SCORE ↓</SS.Chip>
            <SS.Chip>EXPORT</SS.Chip>
          </>}/>
          <div style={{padding:'14px 18px',display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            {filtered.length === 0 && (
              <div style={{gridColumn:'1 / -1',textAlign:'center',padding:'40px 0',color:'var(--fg-4)',fontFamily:'JetBrains Mono,monospace',fontSize:12,letterSpacing:'.18em',textTransform:'uppercase'}}>// no signals match filters</div>
            )}
            {filtered.map(s => <SignalCard key={s.id} sig={s} onSelect={setSelected} selected={selected && selected.id===s.id}/>)}
          </div>
        </section>

        {/* Right rail */}
        <div className="col">
          {t.showRadar && (
            <section className="panel">
              <SS.SectionHead title="Radar" right={<SS.Chip kind="accent">{armedCount} HOT</SS.Chip>}/>
              <div style={{padding:'14px 18px'}}>
                <ScannerRadar signals={filtered}/>
              </div>
            </section>
          )}

          <section className="panel">
            <SS.SectionHead title="Console" right={<SS.Chip kind="amber">// LIVE</SS.Chip>}/>
            <div style={{padding:'12px 14px',background:'rgba(0,0,0,.45)',maxHeight:340,overflowY:'auto'}}>
              <div className="term" style={{fontSize:11,color:'var(--accent)',marginBottom:8,opacity:.85}}>{`> tail -f scanner.log`}<span className="cursor-blink">_</span></div>
              {logs.map((l,i)=>(
                <div className="log-row" key={i} style={{gridTemplateColumns:'46px 36px 1fr 32px'}}>
                  <span className="t">{l.t}</span>
                  <span className={l.passed?'pass':'rej'}>{l.passed?'PASS':'FILT'}</span>
                  <span><span className="sym">{l.sym}</span><br/><span style={{color:'var(--fg-3)',fontSize:10}}>{l.reason}</span></span>
                  <span className="mono" style={{fontSize:10,color:l.passed?'var(--green-soft)':'var(--fg-4)',textAlign:'right'}}>{l.conf.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <SS.SectionHead title="Setup Bias"/>
            <div style={{padding:'14px 18px',display:'flex',flexDirection:'column',gap:8}}>
              {[
                {k:'OB+FVG',c:'var(--cyan)',  v:42},
                {k:'BOS',   c:'var(--purple)',v:28},
                {k:'CHoCH', c:'var(--purple)',v:18},
                {k:'LIQ-SWEEP',c:'var(--amber)',v:25},
                {k:'BREAKER',c:'var(--red-2)', v:14},
              ].map(x => (
                <div key={x.k} style={{display:'flex',alignItems:'center',gap:8}}>
                  <span className="mono" style={{fontSize:10,color:'var(--fg-3)',width:80}}>{x.k}</span>
                  <div style={{flex:1,height:6,background:'rgba(0,0,0,.4)',borderRadius:3,border:'1px solid var(--border-soft)',overflow:'hidden'}}>
                    <div style={{height:'100%',width:Math.min(100,x.v*2)+'%',background:x.c,boxShadow:`0 0 6px ${x.c}`}}/>
                  </div>
                  <span className="mono" style={{fontSize:10,color:'var(--fg)',fontWeight:700,width:32,textAlign:'right'}}>{x.v}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      <SS.FooterStatus now={now} latency={42}/>

      {selected && <SignalDetail sig={selected} onClose={()=>setSelected(null)} onTake={s=>{setSelected(null);}}/>}

      <window.TweaksPanel title="Tweaks" defaultOpen={false}>
        <SS.SharedTweaksControls t={t} setTweak={setTweak}/>
        <window.TweakSection title="Scanner">
          <window.TweakToggle label="Show Radar" value={t.showRadar} onChange={v=>setTweak('showRadar',v)}/>
          <window.TweakToggle label="Auto-Execute" value={t.autoExecute} onChange={v=>setTweak('autoExecute',v)} hint="Bot takes signals automatically"/>
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

// ── TRAINING GROUND — hub of training modules ────────────────
const TgSS = window.SS;

const MODULES = [
  {
    id:'range', label:'RANGE', tag:'Live-fire paper trader',
    color:'#22d3ee',
    body:'Ghost — autonomous bot armed on simulated capital. Same engine as the live bot, no real funds. Generates the trade data the ML model trains on.',
    stat:[{k:'Status',v:'● ARMED',vc:'#4ade80'},{k:'Sim Equity',v:'$5,842'},{k:'Win',v:'61%'}],
    cta:'ENTER RANGE'
  },
  {
    id:'drills', label:'DRILLS', tag:'ML model training',
    color:'#c084fc',
    body:'Train the bot on Ghost\'s closed paper trades. Promote new params to the live bot when the model beats baseline — or reset the model to factory defaults.',
    stat:[{k:'Model',v:'v0.17',vc:'#c084fc'},{k:'vs Baseline',v:'+8.2%',vc:'#4ade80'},{k:'Samples',v:'2,418'}],
    cta:'OPEN DRILLS'
  },
  {
    id:'replay', label:'REPLAY', tag:'Historical setup walkthrough',
    color:'#fbbf24',
    body:'Step through real past trades candle-by-candle. See the entry trigger, stop placement, and exit logic exactly as the bot saw it.',
    stat:[{k:'Library',v:'412 setups'},{k:'Last',v:'SOL · LIQ-SWP'},{k:'Yours',v:'47 viewed'}],
    cta:'START REPLAY'
  },
  {
    id:'quizzes', label:'QUIZZES', tag:'Pattern recognition tests',
    color:'#60a5fa',
    body:'Grade A/B/C/D drills on order blocks, liquidity sweeps, structure breaks. Build the eye before you trust the bot.',
    stat:[{k:'Bank',v:'128 questions'},{k:'Streak',v:'7 day'},{k:'Score',v:'82%',vc:'#4ade80'}],
    cta:'TAKE QUIZ'
  },
  {
    id:'lessons', label:'LESSONS', tag:'Strategy library',
    color:'#4ade80',
    body:'Read-up on every setup the bot trades. Order blocks, FVGs, liquidity sweeps, regime detection, position sizing.',
    stat:[{k:'Chapters',v:'8'},{k:'Done',v:'3 of 8'},{k:'Next',v:'Ch.04 BOS'}],
    cta:'OPEN LIBRARY'
  },
];

function ModCard({ m }){
  return (
    <a href={`#${m.id}`} className="tg-card" style={{borderColor:`color-mix(in oklch, ${m.color} 30%, var(--border-soft))`}}>
      <div className="tg-card-head">
        <div className="tg-card-title" style={{color:m.color}}>
          <span className="mono" style={{fontSize:11,letterSpacing:'.32em',opacity:.6,marginRight:8}}>{m.id.toUpperCase().padStart(2,'0').slice(0,2)}</span>
          {m.label}
        </div>
        <div className="tg-card-tag mono">{m.tag}</div>
      </div>
      <div className="tg-card-body">{m.body}</div>
      <div className="tg-card-stats">
        {m.stat.map((s,i)=>(
          <div key={i}>
            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>{s.k}</div>
            <div className="mono" style={{fontSize:13,color:s.vc||'var(--fg)',fontWeight:700,marginTop:2}}>{s.v}</div>
          </div>
        ))}
      </div>
      <div className="tg-card-cta mono" style={{color:m.color}}>{m.cta} →</div>
      <div className="tg-card-deco" style={{color:m.color}}>
        <svg viewBox="-50 -50 100 100" width="100%" height="100%">
          <circle r="44" fill="none" stroke="currentColor" strokeOpacity=".2" strokeWidth=".5" strokeDasharray="2 4"/>
          <circle r="30" fill="none" stroke="currentColor" strokeOpacity=".15" strokeWidth=".5"/>
        </svg>
      </div>
    </a>
  );
}

// ── Drills (ML) panel — inline, expanded when hash=#drills ────
function DrillsPanel(){
  const [training, setTraining] = useState(false);
  const [progress, setProgress] = useState(0);
  const [modelVer, setModelVer] = useState(17);
  const [accuracy, setAccuracy] = useState(74.2);
  const [baseline] = useState(66.0);
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmPromote, setConfirmPromote] = useState(false);
  const [flash, setFlash] = useState(null);

  useEffect(()=>{
    if (!training) return;
    setProgress(0);
    const id = setInterval(()=>{
      setProgress(p=>{
        if (p>=100){
          clearInterval(id);
          setTraining(false);
          setModelVer(v=>v+1);
          setAccuracy(a=> Math.min(94, a + (Math.random()*2.4 - .4)));
          setFlash({type:'ok',msg:`Model v0.${modelVer+1} trained. Accuracy ${(accuracy + (Math.random()*2)).toFixed(1)}% · ready to promote.`});
          setTimeout(()=>setFlash(null), 5000);
          return 100;
        }
        return p + (1.5 + Math.random()*2);
      });
    }, 80);
    return ()=>clearInterval(id);
  },[training]);

  const FEATURES = [
    {f:'OB Confluence',     w:0.86, c:'#c084fc'},
    {f:'Liquidity Sweep',   w:0.78, c:'#c084fc'},
    {f:'HTF Alignment',     w:0.71, c:'#c084fc'},
    {f:'Volume Expansion',  w:0.62, c:'#c084fc'},
    {f:'BTC Correlation',   w:0.54, c:'#c084fc'},
    {f:'Funding Rate',      w:0.48, c:'#c084fc'},
    {f:'Session Bias',      w:0.39, c:'#c084fc'},
    {f:'RSI Divergence',    w:0.21, c:'#fbbf24'},
    {f:'EMA Cross',         w:0.08, c:'#f87171'},
  ];

  return (
    <section className="panel panel-accent" id="drills" style={{marginTop:18}}>
      <TgSS.Reticle/>
      <div className="corner-tag tl">// ML-DRILLS-ENGINE</div>
      <div className="corner-tag tr">{training?'● TRAINING':'○ READY'}</div>
      <TgSS.SectionHead title="Drills · ML Training" right={<>
        <TgSS.Chip kind="purple">MODEL v0.{modelVer}</TgSS.Chip>
        <TgSS.Chip kind={accuracy>baseline?'green':'red'}>{accuracy>baseline?'▲':'▼'} {((accuracy-baseline)/baseline*100).toFixed(1)}% vs BASELINE</TgSS.Chip>
      </>}/>
      <div style={{padding:'18px 22px'}}>
        <div className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:14,lineHeight:1.5}}>
          // Train the bot on Ghost's closed paper trades. Promote to live when accuracy beats baseline.
        </div>

        {flash && (
          <div style={{padding:'10px 14px',marginBottom:14,border:'1px solid var(--green-border)',background:'rgba(34,197,94,.08)',borderRadius:8,color:'var(--green-soft)',fontFamily:'JetBrains Mono,monospace',fontSize:12}}>● {flash.msg}</div>
        )}

        <div style={{display:'grid',gridTemplateColumns:'1.2fr 1fr',gap:18,marginBottom:18}}>
          {/* training control */}
          <div style={{padding:'16px 18px',border:'1px solid var(--border-soft)',borderRadius:8,background:'rgba(0,0,0,.4)'}}>
            <div className="mono" style={{fontSize:10,color:'#c084fc',letterSpacing:'.2em',marginBottom:10}}>// TRAINING RUN</div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,marginBottom:14}}>
              <div><div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.16em'}}>SAMPLES</div><div className="mono" style={{fontSize:18,color:'var(--fg)',fontWeight:700}}>2,418</div></div>
              <div><div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.16em'}}>EPOCHS</div><div className="mono" style={{fontSize:18,color:'var(--fg)',fontWeight:700}}>140</div></div>
              <div><div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.16em'}}>LR</div><div className="mono" style={{fontSize:18,color:'var(--fg)',fontWeight:700}}>3e-4</div></div>
            </div>
            <div style={{marginBottom:10}}>
              <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                <span className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.18em'}}>{training?'TRAINING…':'IDLE'}</span>
                <span className="mono" style={{fontSize:10,color:'#c084fc',fontWeight:700}}>{progress.toFixed(0)}%</span>
              </div>
              <div style={{height:8,background:'rgba(0,0,0,.6)',borderRadius:4,overflow:'hidden',border:'1px solid var(--border-soft)'}}>
                <div style={{height:'100%',width:progress+'%',background:'linear-gradient(90deg,#c084fc,#a855f7)',boxShadow:'0 0 12px #c084fc',transition:'width .12s'}}/>
              </div>
            </div>
            <button className="btn" disabled={training} onClick={()=>setTraining(true)} style={{width:'100%',padding:'12px',fontSize:12,fontWeight:800,letterSpacing:'.2em',background:training?'rgba(0,0,0,.4)':'#c084fc',color:training?'var(--fg-3)':'#1a1027',border:'none',cursor:training?'not-allowed':'pointer',opacity:training?.6:1}}>
              {training?'■ TRAINING IN PROGRESS':'▶ START TRAINING RUN'}
            </button>
          </div>

          {/* metrics */}
          <div style={{padding:'16px 18px',border:'1px solid var(--border-soft)',borderRadius:8,background:'rgba(0,0,0,.4)'}}>
            <div className="mono" style={{fontSize:10,color:'#c084fc',letterSpacing:'.2em',marginBottom:14}}>// MODEL ACCURACY (7d)</div>
            <svg viewBox="0 0 280 100" style={{width:'100%',height:90}}>
              <line x1="0" y1={100-(baseline-50)*2} x2="280" y2={100-(baseline-50)*2} stroke="#fbbf24" strokeWidth="1" strokeDasharray="3 3" opacity=".7"/>
              <text x="2" y={100-(baseline-50)*2 - 4} fill="#fbbf24" fontSize="8" fontFamily="Share Tech Mono">BASELINE {baseline}%</text>
              <polyline fill="none" stroke="#c084fc" strokeWidth="2" points={
                Array.from({length:14},(_,i)=>{
                  const x = (i/13)*280;
                  const a = 66 + i*0.6 + Math.sin(i*0.7)*1.2;
                  return `${x},${100-(a-50)*2}`;
                }).join(' ')
              } style={{filter:'drop-shadow(0 0 4px #c084fc)'}}/>
              <circle cx="280" cy={100-(accuracy-50)*2} r="4" fill="#c084fc"/>
              <text x="270" y={100-(accuracy-50)*2 - 8} fill="#c084fc" fontSize="9" fontFamily="JetBrains Mono" fontWeight="700" textAnchor="end">{accuracy.toFixed(1)}%</text>
            </svg>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginTop:8}}>
              <div><div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.16em'}}>PRECISION</div><div className="mono" style={{fontSize:14,color:'var(--green-soft)',fontWeight:700}}>78.4%</div></div>
              <div><div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.16em'}}>RECALL</div><div className="mono" style={{fontSize:14,color:'#c084fc',fontWeight:700}}>71.2%</div></div>
            </div>
          </div>
        </div>

        {/* feature importance */}
        <div className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// FEATURE IMPORTANCE</div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:18}}>
          {FEATURES.map(f=>(
            <div key={f.f} style={{display:'grid',gridTemplateColumns:'140px 1fr 50px',gap:8,alignItems:'center',padding:'4px 10px',background:'rgba(0,0,0,.3)',border:'1px solid var(--border-soft)',borderRadius:4}}>
              <span className="mono" style={{fontSize:11,color:'var(--fg-2)'}}>{f.f}</span>
              <div style={{height:6,background:'rgba(0,0,0,.6)',borderRadius:3,overflow:'hidden'}}>
                <div style={{width:(f.w*100)+'%',height:'100%',background:f.c,boxShadow:`0 0 6px ${f.c}`}}/>
              </div>
              <span className="mono" style={{fontSize:11,color:f.c,fontWeight:700,textAlign:'right'}}>{f.w.toFixed(2)}</span>
            </div>
          ))}
        </div>

        {/* Action row: Promote + Reset */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
          {/* promote */}
          <div style={{padding:'16px 18px',border:'1.5px solid var(--green-border)',borderRadius:8,background:'rgba(34,197,94,.06)'}}>
            <div className="mono" style={{fontSize:10,color:'var(--green-soft)',letterSpacing:'.2em',marginBottom:6}}>// PROMOTE TO LIVE BOT</div>
            <div style={{fontSize:12,color:'var(--fg-2)',lineHeight:1.5,marginBottom:12}}>Push model v0.{modelVer} parameters to the live Bot. Existing positions stay untouched; next signal uses new weights.</div>
            {!confirmPromote ? (
              <button className="btn btn-green" onClick={()=>setConfirmPromote(true)} style={{width:'100%',padding:'10px',fontWeight:800,letterSpacing:'.18em',fontSize:11}} disabled={accuracy<=baseline}>↑ PROMOTE TO LIVE</button>
            ) : (
              <div style={{display:'flex',gap:6}}>
                <button className="btn" style={{flex:1,padding:'10px',fontSize:11}} onClick={()=>setConfirmPromote(false)}>CANCEL</button>
                <button className="btn btn-green" style={{flex:1,padding:'10px',fontSize:11,fontWeight:800}} onClick={()=>{setConfirmPromote(false);setFlash({type:'ok',msg:`Model v0.${modelVer} promoted to live bot. Parameters synced to Phemex.`});setTimeout(()=>setFlash(null),5000);}}>▶ CONFIRM</button>
              </div>
            )}
            {accuracy<=baseline && <div className="mono" style={{fontSize:9,color:'var(--amber)',letterSpacing:'.14em',marginTop:8}}>⚠ accuracy must beat baseline to promote</div>}
          </div>
          {/* reset */}
          <div style={{padding:'16px 18px',border:'1.5px solid var(--red-border)',borderRadius:8,background:'rgba(248,113,113,.06)'}}>
            <div className="mono" style={{fontSize:10,color:'var(--red-2)',letterSpacing:'.2em',marginBottom:6}}>// RESET ML MEMORY</div>
            <div style={{fontSize:12,color:'var(--fg-2)',lineHeight:1.5,marginBottom:12}}>Wipe all trained weights. Returns the bot to factory baseline (v0.0). All Ghost trade history retained — only the model resets.</div>
            {!confirmReset ? (
              <button className="btn btn-red" onClick={()=>setConfirmReset(true)} style={{width:'100%',padding:'10px',fontWeight:800,letterSpacing:'.18em',fontSize:11}}>↺ RESET TO FACTORY</button>
            ) : (
              <div style={{display:'flex',gap:6}}>
                <button className="btn" style={{flex:1,padding:'10px',fontSize:11}} onClick={()=>setConfirmReset(false)}>CANCEL</button>
                <button className="btn btn-red" style={{flex:1,padding:'10px',fontSize:11,fontWeight:800}} onClick={()=>{setConfirmReset(false);setModelVer(0);setAccuracy(66.0);setFlash({type:'warn',msg:'Model reset to factory v0.0 baseline. ML memory cleared.'});setTimeout(()=>setFlash(null),5000);}}>↺ CONFIRM RESET</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function App(){
  const [t, setTweak] = window.useTweaks({ ...TgSS.SHARED_TWEAK_DEFAULTS });
  useEffect(()=>{ TgSS.applyTweaks(t, 'cyan'); },[t]);
  const [now, setNow] = useState(Date.now());
  useEffect(()=>{ const id=setInterval(()=>setNow(Date.now()),1000); return ()=>clearInterval(id); },[]);

  const TweaksPanel = window.TweaksPanel;

  return (
    <div className="page">
      <TgSS.Topbar active="training" now={now}/>
      <TgSS.PageHead
        icon={<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" style={{color:'var(--accent)'}}/><circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" style={{color:'var(--accent)'}}/><circle cx="12" cy="12" r="1.5" fill="currentColor" style={{color:'var(--accent)'}}/></svg>}
        title="Training Ground"
        subtitle="Hub · Range · Drills · Replay · Quizzes · Lessons — practice the system, train the model"
        accent="cyan"
        badges={<>
          <TgSS.Chip kind="cyan">● 5 MODULES</TgSS.Chip>
          <TgSS.Chip kind="green">GHOST · ARMED</TgSS.Chip>
          <TgSS.Chip kind="purple">MODEL v0.17</TgSS.Chip>
        </>}
      />

      <div className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.24em',textTransform:'uppercase',margin:'10px 4px 14px',display:'flex',alignItems:'center',gap:14}}>
        <div style={{flex:1,height:1,background:'linear-gradient(90deg,transparent,var(--border-soft),transparent)'}}/>
        <span>// SELECT A TRAINING MODULE</span>
        <div style={{flex:1,height:1,background:'linear-gradient(90deg,transparent,var(--border-soft),transparent)'}}/>
      </div>

      <div className="tg-grid">
        {MODULES.map(m=> <ModCard key={m.id} m={m}/>)}
      </div>

      <DrillsPanel/>

      <TgSS.FooterStatus now={now}/>

      {TweaksPanel && <TweaksPanel title="Tweaks">
        <TgSS.SharedTweaksControls t={t} setTweak={setTweak}/>
      </TweaksPanel>}

      <style>{`
        .tg-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
        @media (max-width:1100px){.tg-grid{grid-template-columns:repeat(2,1fr)}}
        @media (max-width:700px){.tg-grid{grid-template-columns:1fr}}
        .tg-card{position:relative;display:flex;flex-direction:column;gap:10px;padding:18px 20px;border:1px solid var(--border-soft);border-radius:12px;background:linear-gradient(135deg,rgba(0,0,0,.55),oklch(0.22 0.010 125 / .55));text-decoration:none;color:inherit;overflow:hidden;transition:transform .2s,box-shadow .2s;min-height:230px}
        .tg-card:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.4)}
        .tg-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
        .tg-card-title{font-family:'Share Tech Mono',monospace;font-size:24px;letter-spacing:.16em;text-transform:uppercase}
        .tg-card-tag{font-size:10px;color:var(--fg-4);letter-spacing:.2em;text-transform:uppercase;text-align:right;max-width:140px;line-height:1.4}
        .tg-card-body{font-size:13px;color:var(--fg-2);line-height:1.5;flex:1}
        .tg-card-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 0;border-top:1px dashed var(--border-soft);border-bottom:1px dashed var(--border-soft)}
        .tg-card-cta{font-size:11px;letter-spacing:.24em;font-weight:700;padding-top:4px}
        .tg-card-deco{position:absolute;right:-30px;bottom:-30px;width:130px;height:130px;opacity:.5;pointer-events:none}
      `}</style>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

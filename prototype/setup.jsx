// ── BOT SETUP — strategy, risk, execution, exchanges, presets
const SS = window.SS;

const PRESETS = [
  { id:'sniper',     name:'SNIPER',      desc:'High-conf only · A+ setups · 0.5–1.5R',  risk:1.0, conf:8.0, lev:5,  freq:'low',    accent:'red' },
  { id:'tactical',   name:'TACTICAL',    desc:'Balanced · OB/FVG + structure',          risk:1.5, conf:7.0, lev:5,  freq:'medium', accent:'amber' },
  { id:'aggressive', name:'AGGRESSIVE',  desc:'More signals · faster scalps',           risk:2.0, conf:6.0, lev:8,  freq:'high',   accent:'green' },
  { id:'stealth',    name:'STEALTH',     desc:'Hidden orders · iceberg · low footprint',risk:1.0, conf:7.5, lev:4,  freq:'medium', accent:'cyan' },
];

const SETUPS = ['OB+FVG','BOS','CHoCH','LIQ-SWEEP','OB-RETEST','FVG-FILL','BREAKER'];
const TFS = ['1m','5m','15m','1h','4h','1D'];
const SESSIONS = [
  { id:'asia', name:'ASIA',  hours:'00:00 – 08:00 UTC' },
  { id:'eu',   name:'LONDON',hours:'08:00 – 16:00 UTC' },
  { id:'us',   name:'NY',    hours:'13:00 – 21:00 UTC' },
];
const EXCHANGES = [
  { id:'bybit',   name:'BYBIT',   status:'connected', balance:'$5,842.18', acct:'••••8421', latency:38 },
  { id:'binance', name:'BINANCE', status:'connected', balance:'$2,140.00', acct:'••••0033', latency:42 },
  { id:'okx',     name:'OKX',     status:'disconnected', balance:'—', acct:'—', latency:null },
  { id:'bitget',  name:'BITGET',  status:'disconnected', balance:'—', acct:'—', latency:null },
];

function Toggle({ value, onChange, hint, label, disabled }){
  return (
    <div onClick={()=>!disabled && onChange(!value)} style={{display:'flex',alignItems:'center',gap:12,padding:'10px 12px',border:'1px solid var(--border-soft)',borderRadius:6,background:'rgba(0,0,0,.3)',cursor:disabled?'not-allowed':'pointer',opacity:disabled?0.5:1,transition:'all .15s'}}>
      <div style={{width:36,height:18,borderRadius:9,background:value?'var(--accent)':'rgba(0,0,0,.6)',position:'relative',flexShrink:0,border:'1px solid var(--border-soft)',boxShadow:value?'0 0 8px var(--accent)':'none',transition:'all .15s'}}>
        <div style={{position:'absolute',top:1,left:value?19:1,width:14,height:14,borderRadius:'50%',background:value?'#0a0c0e':'var(--fg-3)',transition:'left .15s'}}/>
      </div>
      <div style={{flex:1,minWidth:0}}>
        <div style={{fontFamily:'Share Tech Mono,monospace',fontSize:12,letterSpacing:'.05em',color:'var(--fg)'}}>{label}</div>
        {hint && <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.1em',marginTop:2}}>{hint}</div>}
      </div>
      <span className="mono" style={{fontSize:9,color:value?'var(--green-soft)':'var(--fg-4)',letterSpacing:'.18em'}}>{value?'ENGAGED':'OFF'}</span>
    </div>
  );
}

function Slider({ label, value, min, max, step, onChange, suffix, color }){
  return (
    <div style={{padding:'12px 14px',border:'1px solid var(--border-soft)',borderRadius:6,background:'rgba(0,0,0,.3)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
        <span className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.16em',textTransform:'uppercase'}}>{label}</span>
        <span className="mono" style={{fontSize:14,fontWeight:800,color:color||'var(--accent)'}}>{value}{suffix||''}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e=>onChange(+e.target.value)} style={{width:'100%'}}/>
      <div style={{display:'flex',justifyContent:'space-between',marginTop:2}}>
        <span className="mono" style={{fontSize:8,color:'var(--fg-4)'}}>{min}{suffix||''}</span>
        <span className="mono" style={{fontSize:8,color:'var(--fg-4)'}}>{max}{suffix||''}</span>
      </div>
    </div>
  );
}

function Section({ title, num, desc, children }){
  return (
    <section className="panel" style={{marginBottom:14}}>
      <div style={{padding:'14px 18px',borderBottom:'1px solid var(--border-soft)',background:'rgba(0,0,0,.4)',display:'flex',alignItems:'center',gap:14}}>
        <span style={{display:'inline-flex',alignItems:'center',justifyContent:'center',width:32,height:32,border:'1px solid var(--accent)',color:'var(--accent)',fontFamily:'JetBrains Mono,monospace',fontSize:11,fontWeight:700,letterSpacing:'.08em',borderRadius:3,boxShadow:'0 0 8px rgba(34,211,238,.2)'}}>{num}</span>
        <div style={{flex:1}}>
          <div style={{fontFamily:'Share Tech Mono,monospace',fontSize:15,letterSpacing:'.08em',color:'var(--fg)',textTransform:'uppercase'}}>{title}</div>
          {desc && <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.1em',marginTop:2}}>{desc}</div>}
        </div>
      </div>
      <div style={{padding:'14px 18px'}}>{children}</div>
    </section>
  );
}

function SetupApp(){
  const [t, setTweak] = window.useTweaks({
    ...SS.SHARED_TWEAK_DEFAULTS,
    preset: 'tactical',
    riskPerTrade: 1.5,
    maxConcurrent: 3,
    leverage: 5,
    minConf: 7.0,
    dailyDDStop: 5,
    weeklyDDStop: 12,
    selectedSetups: ['OB+FVG','BOS','CHoCH','LIQ-SWEEP','OB-RETEST','FVG-FILL'],
    selectedTfs: ['15m','1h','4h'],
    selectedSessions: ['eu','us'],
    selectedExchanges: ['bybit','binance'],
    autoExecute: true,
    martingale: false,
    avgIn: false,
    trailStop: true,
    breakeven: true,
    notifyDiscord: true,
    notifyTg: false,
    notifyEmail: false,
    btcVeto: true,
    fundingFilter: true,
    spreadFilter: true,
  });
  useEffect(()=>{ SS.applyTweaks(t, 'cyan'); }, [t]);

  const [now, setNow] = useState(Date.now());
  const [savedFlash, setSavedFlash] = useState(false);
  const [confirmDeploy, setConfirmDeploy] = useState(false);
  useEffect(()=>{
    const id = setInterval(()=>setNow(Date.now()), 1000);
    return ()=>clearInterval(id);
  },[]);

  const toggleArr = (key, val) => {
    const set = new Set(t[key]);
    if (set.has(val)) set.delete(val); else set.add(val);
    setTweak(key, [...set]);
  };

  const applyPreset = (p) => {
    setTweak({ preset:p.id, riskPerTrade:p.risk, minConf:p.conf, leverage:p.lev });
  };

  const onSave = () => { setSavedFlash(true); setTimeout(()=>setSavedFlash(false), 1600); };

  // Risk preview
  const balance = 5842.18;
  const riskUsd = (balance * t.riskPerTrade) / 100;
  const positionUsd = riskUsd * t.leverage;
  const dailyMaxUsd = (balance * t.dailyDDStop) / 100;

  return (
    <div>
      {!window.__BOT_SHELL__ && <SS.Topbar active="setup" now={now}/>}
      <SS.PageHead
        icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <circle cx="6" cy="6" r="2" stroke="var(--accent)" strokeWidth="1.6"/>
          <line x1="9" y1="6" x2="22" y2="6" stroke="var(--accent)" strokeWidth="1.6"/>
          <circle cx="16" cy="12" r="2" stroke="var(--accent)" strokeWidth="1.6"/>
          <line x1="2" y1="12" x2="13" y2="12" stroke="var(--accent)" strokeWidth="1.6"/>
          <line x1="19" y1="12" x2="22" y2="12" stroke="var(--accent)" strokeWidth="1.6"/>
          <circle cx="9" cy="18" r="2" stroke="var(--accent)" strokeWidth="1.6"/>
          <line x1="2" y1="18" x2="6" y2="18" stroke="var(--accent)" strokeWidth="1.6"/>
          <line x1="12" y1="18" x2="22" y2="18" stroke="var(--accent)" strokeWidth="1.6"/>
        </svg>}
        title="Bot Setup"
        subtitle="strategy · risk · execution · exchanges"
        badges={<>
          <SS.Chip kind="cyan">PRESET · {(PRESETS.find(p=>p.id===t.preset)||PRESETS[1]).name}</SS.Chip>
          <SS.Chip kind={savedFlash?'green':'amber'}>{savedFlash?'✓ SAVED':'● UNSAVED'}</SS.Chip>
          <button className="btn btn-cyan" style={{padding:'6px 12px'}} onClick={onSave}>SAVE CONFIG</button>
        </>}
      />

      {/* Top — preset selector + apply */}
      <section className="panel panel-accent" style={{marginBottom:18}}>
        <SS.Reticle/>
        <div className="corner-tag tl">// MODE-SELECT</div>
        <div className="corner-tag tr">PHANTOM ENGINE / 4 PROFILES</div>
        <div style={{padding:'18px 22px'}}>
          <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.20em',textTransform:'uppercase',marginBottom:12}}>// SELECT OPERATING PROFILE</div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(4, 1fr)',gap:12}}>
            {PRESETS.map(p => {
              const active = t.preset === p.id;
              const colorMap = { red:'var(--red-2)', amber:'var(--amber)', green:'var(--green-soft)', cyan:'var(--cyan)' };
              const c = colorMap[p.accent];
              return (
                <button key={p.id} onClick={()=>applyPreset(p)} style={{textAlign:'left',padding:'16px 14px',border:`1.5px solid ${active?c:'var(--border-soft)'}`,background:active?`rgba(0,0,0,.5)`:'rgba(0,0,0,.3)',borderRadius:8,cursor:'pointer',position:'relative',overflow:'hidden',transition:'all .2s',boxShadow:active?`0 0 16px ${c}55, inset 0 0 0 1px ${c}33`:'none'}}>
                  {active && <div style={{position:'absolute',top:0,left:0,right:0,height:2,background:c,boxShadow:`0 0 8px ${c}`}}/>}
                  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
                    <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:18,letterSpacing:'.1em',color:active?c:'var(--fg-2)',fontWeight:700}}>{p.name}</span>
                    {active && <span className="mono" style={{fontSize:9,color:c,letterSpacing:'.18em',padding:'2px 6px',border:`1px solid ${c}`,borderRadius:3}}>ACTIVE</span>}
                  </div>
                  <div style={{fontSize:11,color:'var(--fg-3)',marginBottom:10,lineHeight:1.4}}>{p.desc}</div>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:6,paddingTop:10,borderTop:`1px dashed ${active?c+'66':'var(--border-soft)'}`}}>
                    <div><div className="mono" style={{fontSize:8,color:'var(--fg-4)',letterSpacing:'.14em'}}>RISK</div><div className="mono" style={{fontSize:11,color:'var(--fg)',fontWeight:700}}>{p.risk}%</div></div>
                    <div><div className="mono" style={{fontSize:8,color:'var(--fg-4)',letterSpacing:'.14em'}}>CONF</div><div className="mono" style={{fontSize:11,color:'var(--fg)',fontWeight:700}}>≥{p.conf}</div></div>
                    <div><div className="mono" style={{fontSize:8,color:'var(--fg-4)',letterSpacing:'.14em'}}>LEV</div><div className="mono" style={{fontSize:11,color:'var(--fg)',fontWeight:700}}>{p.lev}×</div></div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <div style={{display:'grid',gridTemplateColumns:'1fr 320px',gap:14,alignItems:'start'}}>
        {/* MAIN */}
        <div>
          {/* RISK */}
          <Section title="Risk Engine" num="01" desc="position sizing · loss limits · concurrent exposure">
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:10}}>
              <Slider label="Risk per Trade"   value={t.riskPerTrade}  min={0.25} max={5} step={0.25} suffix="%"  onChange={v=>setTweak('riskPerTrade',v)} color="var(--amber)"/>
              <Slider label="Max Concurrent"   value={t.maxConcurrent} min={1}    max={10} step={1}  suffix=" pos" onChange={v=>setTweak('maxConcurrent',v)}/>
              <Slider label="Leverage"          value={t.leverage}      min={1}    max={20} step={1}  suffix="×"   onChange={v=>setTweak('leverage',v)} color={t.leverage>10?'var(--red-2)':t.leverage>5?'var(--amber)':'var(--green-soft)'}/>
              <Slider label="Min Confidence"    value={t.minConf}       min={5}    max={10} step={0.1} onChange={v=>setTweak('minConf',v)}/>
              <Slider label="Daily DD Stop"     value={t.dailyDDStop}   min={1}    max={15} step={0.5} suffix="%"   onChange={v=>setTweak('dailyDDStop',v)} color="var(--red-2)"/>
              <Slider label="Weekly DD Stop"    value={t.weeklyDDStop}  min={3}    max={30} step={1}    suffix="%"   onChange={v=>setTweak('weeklyDDStop',v)} color="var(--red-2)"/>
            </div>
            {/* Risk preview tile */}
            <div style={{marginTop:8,padding:'14px 16px',border:'1px dashed var(--accent)',borderRadius:6,background:'rgba(34,211,238,.05)'}}>
              <div className="mono" style={{fontSize:9,color:'var(--accent)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:10}}>// LIVE RISK PREVIEW · BAL ${balance.toLocaleString()}</div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:10}}>
                <div className="metric-tile"><div className="metric-label">Risk / Trade</div><div className="metric-value" style={{color:'var(--amber)'}}>${riskUsd.toFixed(2)}</div><div className="metric-sub">{t.riskPerTrade}% of equity</div></div>
                <div className="metric-tile"><div className="metric-label">Position Size</div><div className="metric-value">${positionUsd.toFixed(0)}</div><div className="metric-sub">@ {t.leverage}× lev</div></div>
                <div className="metric-tile"><div className="metric-label">Max Daily Loss</div><div className="metric-value" style={{color:'var(--red-2)'}}>-${dailyMaxUsd.toFixed(0)}</div><div className="metric-sub">kills bot @ -{t.dailyDDStop}%</div></div>
                <div className="metric-tile"><div className="metric-label">Max Exposure</div><div className="metric-value">${(positionUsd*t.maxConcurrent).toFixed(0)}</div><div className="metric-sub">{t.maxConcurrent} concurrent</div></div>
              </div>
            </div>
          </Section>

          {/* STRATEGY — setups + tfs */}
          <Section title="Strategy Filter" num="02" desc="setup library · timeframes · sessions">
            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// SETUPS · {t.selectedSetups.length} ENABLED</div>
            <div style={{display:'flex',flexWrap:'wrap',gap:6,marginBottom:14}}>
              {SETUPS.map(s => {
                const active = t.selectedSetups.includes(s);
                return <button key={s} onClick={()=>toggleArr('selectedSetups',s)} className={`btn ${active?'btn-cyan':''}`} style={{padding:'7px 12px',fontSize:11}}>{active?'◉ ':'○ '}{s}</button>;
              })}
            </div>

            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// TIMEFRAMES · {t.selectedTfs.length} ENABLED</div>
            <div style={{display:'flex',gap:6,marginBottom:14}}>
              {TFS.map(tf => {
                const active = t.selectedTfs.includes(tf);
                return <button key={tf} onClick={()=>toggleArr('selectedTfs',tf)} className={`btn ${active?'btn-cyan':''}`} style={{padding:'8px 14px',fontSize:12,flex:1,fontFamily:'JetBrains Mono,monospace'}}>{tf}</button>;
              })}
            </div>

            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:8}}>// SESSIONS · scan only during selected sessions</div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:6}}>
              {SESSIONS.map(s => {
                const active = t.selectedSessions.includes(s.id);
                return (
                  <button key={s.id} onClick={()=>toggleArr('selectedSessions',s.id)} style={{textAlign:'left',padding:'10px 12px',border:`1px solid ${active?'var(--accent)':'var(--border-soft)'}`,background:active?'rgba(34,211,238,.07)':'rgba(0,0,0,.3)',borderRadius:6,cursor:'pointer'}}>
                    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                      <span style={{fontFamily:'Share Tech Mono,monospace',fontSize:12,color:active?'var(--accent)':'var(--fg-2)',letterSpacing:'.08em'}}>{s.name}</span>
                      <span className="mono" style={{fontSize:9,color:active?'var(--green-soft)':'var(--fg-4)',letterSpacing:'.16em'}}>{active?'ON':'OFF'}</span>
                    </div>
                    <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.05em',marginTop:3}}>{s.hours}</div>
                  </button>
                );
              })}
            </div>
          </Section>

          {/* EXECUTION */}
          <Section title="Execution Behavior" num="03" desc="auto-trade rules · stop management · safety filters">
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
              <Toggle label="Auto-Execute"        value={t.autoExecute}    hint="bot takes signals automatically (no confirm)" onChange={v=>setTweak('autoExecute',v)}/>
              <Toggle label="Move SL → BE @ TP1"  value={t.breakeven}      hint="lock in zero risk after first target" onChange={v=>setTweak('breakeven',v)}/>
              <Toggle label="Trailing Stop"       value={t.trailStop}      hint="trail by ATR after TP1" onChange={v=>setTweak('trailStop',v)}/>
              <Toggle label="BTC Veto Filter"      value={t.btcVeto}        hint="block alt longs if BTC down >2% in 1h" onChange={v=>setTweak('btcVeto',v)}/>
              <Toggle label="Funding Rate Filter"  value={t.fundingFilter}  hint="skip when funding extreme (>0.1%)" onChange={v=>setTweak('fundingFilter',v)}/>
              <Toggle label="Spread Filter"        value={t.spreadFilter}   hint="reject when spread > 0.05%" onChange={v=>setTweak('spreadFilter',v)}/>
              <Toggle label="Average-In on Pullback" value={t.avgIn}        hint="add second tranche at -0.5R (advanced)" onChange={v=>setTweak('avgIn',v)}/>
              <Toggle label="Martingale (DANGER)"  value={t.martingale}     hint="size up after losses · disabled by default" onChange={v=>setTweak('martingale',v)}/>
            </div>
          </Section>

          {/* EXCHANGES */}
          <Section title="Exchange Routing" num="04" desc="API keys · venue selection · per-account limits">
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {EXCHANGES.map(ex => {
                const enabled = t.selectedExchanges.includes(ex.id);
                const conn = ex.status === 'connected';
                return (
                  <div key={ex.id} style={{display:'grid',gridTemplateColumns:'auto 1fr 90px 130px 100px auto',gap:14,alignItems:'center',padding:'12px 14px',border:`1px solid ${enabled && conn?'rgba(34,197,94,.4)':'var(--border-soft)'}`,borderRadius:6,background:enabled && conn?'rgba(34,197,94,.04)':'rgba(0,0,0,.3)'}}>
                    <div style={{width:36,height:36,border:'1px solid var(--border-soft)',borderRadius:4,display:'flex',alignItems:'center',justifyContent:'center',fontFamily:'JetBrains Mono,monospace',fontSize:9,color:'var(--accent)',letterSpacing:'.1em',background:'rgba(0,0,0,.4)',fontWeight:700}}>{ex.name.slice(0,2)}</div>
                    <div>
                      <div style={{fontFamily:'Share Tech Mono,monospace',fontSize:14,letterSpacing:'.06em'}}>{ex.name}</div>
                      <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.1em',marginTop:2}}>API · {ex.acct}</div>
                    </div>
                    <SS.Chip kind={conn?'green':'red'}>{conn?'● LIVE':'○ OFFLINE'}</SS.Chip>
                    <div style={{textAlign:'right'}}>
                      <div className="mono" style={{fontSize:13,fontWeight:700,color:conn?'var(--green-soft)':'var(--fg-4)'}}>{ex.balance}</div>
                      <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.12em'}}>{conn?`LATENCY ${ex.latency}ms`:'NOT CONNECTED'}</div>
                    </div>
                    <button className="btn" style={{padding:'6px 10px',fontSize:10}}>{conn?'CONFIGURE':'+ CONNECT'}</button>
                    <Toggle label="" value={enabled && conn} disabled={!conn} onChange={v=>toggleArr('selectedExchanges',ex.id)}/>
                  </div>
                );
              })}
            </div>
            <div style={{marginTop:14,padding:'12px 14px',border:'1px dashed var(--border-soft)',borderRadius:6,display:'flex',justifyContent:'space-between',alignItems:'center',background:'rgba(0,0,0,.25)'}}>
              <div className="mono" style={{fontSize:11,color:'var(--fg-3)',letterSpacing:'.05em'}}>// keys are encrypted at rest · withdrawals always disabled · IP-pinned</div>
              <button className="btn btn-cyan" style={{padding:'6px 12px',fontSize:11}}>+ ADD EXCHANGE</button>
            </div>
          </Section>

          {/* NOTIFICATIONS */}
          <Section title="Notifications" num="05" desc="alerts on entry · exit · errors">
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10}}>
              <Toggle label="Discord Webhook" value={t.notifyDiscord} hint="real-time embeds · #trades" onChange={v=>setTweak('notifyDiscord',v)}/>
              <Toggle label="Telegram"        value={t.notifyTg}      hint="DMs to @user_id" onChange={v=>setTweak('notifyTg',v)}/>
              <Toggle label="Email Digest"    value={t.notifyEmail}   hint="daily summary @ 23:00 UTC" onChange={v=>setTweak('notifyEmail',v)}/>
            </div>
          </Section>
        </div>

        {/* RIGHT SIDEBAR — DEPLOY */}
        <div style={{position:'sticky',top:14}}>
          <section className="panel panel-accent">
            <SS.SectionHead title="Deploy"/>
            <div style={{padding:'18px 16px'}}>
              <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:10}}>// CONFIG SUMMARY</div>
              <div style={{display:'flex',flexDirection:'column',gap:4,fontFamily:'JetBrains Mono,monospace',fontSize:11,marginBottom:14}}>
                {[
                  ['preset',  PRESETS.find(p=>p.id===t.preset)?.name],
                  ['risk',    t.riskPerTrade+'%'],
                  ['leverage',t.leverage+'×'],
                  ['min conf',t.minConf.toFixed(1)],
                  ['setups',  t.selectedSetups.length],
                  ['tfs',     t.selectedTfs.join(', ')],
                  ['sessions',t.selectedSessions.length+'/3'],
                  ['venues',  t.selectedExchanges.length+'/4'],
                  ['auto-exec', t.autoExecute?'YES':'NO'],
                ].map(([k,v]) => (
                  <div key={k} style={{display:'flex',justifyContent:'space-between',padding:'4px 0',borderBottom:'1px dashed var(--border-soft)'}}>
                    <span style={{color:'var(--fg-4)',letterSpacing:'.1em',textTransform:'uppercase',fontSize:9}}>{k}</span>
                    <span style={{color:'var(--fg)',fontWeight:600}}>{v}</span>
                  </div>
                ))}
              </div>

              <div style={{padding:'10px 12px',border:'1px solid var(--amber-2)',background:'rgba(251,191,36,.08)',borderRadius:6,marginBottom:14}}>
                <div className="mono" style={{fontSize:9,color:'var(--amber-2)',letterSpacing:'.16em',textTransform:'uppercase',marginBottom:4}}>⚠ PRE-FLIGHT</div>
                <div style={{fontSize:11,color:'var(--fg-2)',lineHeight:1.5}}>
                  Bot will trade <b style={{color:'var(--accent)'}}>real funds</b> on {t.selectedExchanges.length} venues using <b style={{color:'var(--accent)'}}>{t.riskPerTrade}% risk</b> per trade. Stops auto-managed. Daily kill at -{t.dailyDDStop}%.
                </div>
              </div>

              <div style={{display:'flex',flexDirection:'column',gap:8}}>
                <button className="btn btn-cyan" style={{padding:'12px',fontSize:12}} onClick={onSave}>{savedFlash?'✓ SAVED':'SAVE CONFIG'}</button>
                {!confirmDeploy
                  ? <button className="btn btn-green" style={{padding:'14px',fontSize:13,fontWeight:800,letterSpacing:'.18em'}} onClick={()=>setConfirmDeploy(true)}>▶ DEPLOY BOT</button>
                  : (
                    <div style={{padding:12,border:'2px solid var(--green-soft)',borderRadius:6,background:'rgba(34,197,94,.08)'}}>
                      <div className="mono" style={{fontSize:9,color:'var(--green-soft)',letterSpacing:'.18em',marginBottom:8}}>// CONFIRM DEPLOYMENT</div>
                      <div style={{fontSize:11,color:'var(--fg-2)',marginBottom:12,lineHeight:1.5}}>Bot will go LIVE on next signal. Continue?</div>
                      <div style={{display:'flex',gap:6}}>
                        <button className="btn" style={{flex:1,padding:'8px'}} onClick={()=>setConfirmDeploy(false)}>CANCEL</button>
                        <button className="btn btn-green" style={{flex:1,padding:'8px'}} onClick={()=>{setConfirmDeploy(false); onSave();}}>▶ CONFIRM</button>
                      </div>
                    </div>
                  )
                }
                <button className="btn" style={{padding:'10px',fontSize:10,color:'var(--red-2)',borderColor:'rgba(248,113,113,.4)'}}>↺ RESET TO DEFAULTS</button>
              </div>
            </div>
          </section>

          <section className="panel">
            <SS.SectionHead title="Backtest"/>
            <div style={{padding:'14px 16px'}}>
              <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:10}}>// 90D · CURRENT CONFIG</div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:12}}>
                <div className="metric-tile"><div className="metric-label">PnL</div><div className="metric-value" style={{color:'var(--green-soft)'}}>+34.8%</div></div>
                <div className="metric-tile"><div className="metric-label">Sharpe</div><div className="metric-value" style={{color:'var(--accent)'}}>1.84</div></div>
                <div className="metric-tile"><div className="metric-label">Win Rate</div><div className="metric-value">62%</div></div>
                <div className="metric-tile"><div className="metric-label">Max DD</div><div className="metric-value" style={{color:'var(--red-2)'}}>-8.4%</div></div>
              </div>
              <button className="btn" style={{width:'100%',padding:'8px',fontSize:11}}>▶ RUN BACKTEST</button>
            </div>
          </section>
        </div>
      </div>

      <SS.FooterStatus now={now} latency={28}/>

      <window.TweaksPanel title="Tweaks" defaultOpen={false}>
        <SS.SharedTweaksControls t={t} setTweak={setTweak}/>
      </window.TweaksPanel>
    </div>
  );
}

window.SetupApp = SetupApp;
if (!window.__BOT_SHELL__) ReactDOM.createRoot(document.getElementById('root')).render(<SetupApp/>);

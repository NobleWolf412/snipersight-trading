// ── SETTINGS — account, API keys, notifications, theme ───────
const StSS = window.SS;

function Card({ title, hint, children }){
  return (
    <section className="panel" style={{padding:0}}>
      <StSS.SectionHead title={title}/>
      {hint && <div className="mono" style={{padding:'0 20px',fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:6}}>{hint}</div>}
      <div style={{padding:'14px 20px 18px'}}>{children}</div>
    </section>
  );
}

function Row({ label, hint, children }){
  return (
    <div style={{display:'grid',gridTemplateColumns:'200px 1fr',gap:18,padding:'12px 0',borderBottom:'1px dashed var(--border-soft)',alignItems:'center'}}>
      <div>
        <div className="mono" style={{fontSize:11,color:'var(--fg)',fontWeight:600,letterSpacing:'.06em'}}>{label}</div>
        {hint && <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.14em',textTransform:'uppercase',marginTop:3}}>{hint}</div>}
      </div>
      <div>{children}</div>
    </div>
  );
}

function Toggle({ value, onChange, label }){
  return (
    <div onClick={()=>onChange(!value)} style={{display:'inline-flex',alignItems:'center',gap:10,cursor:'pointer'}}>
      <div style={{width:40,height:20,borderRadius:10,background:value?'var(--accent)':'rgba(0,0,0,.6)',position:'relative',border:'1px solid var(--border-soft)',boxShadow:value?'0 0 8px var(--accent)':'none',transition:'all .15s'}}>
        <div style={{position:'absolute',top:1,left:value?21:1,width:16,height:16,borderRadius:'50%',background:value?'#0a0c0e':'var(--fg-3)',transition:'left .15s'}}/>
      </div>
      <span className="mono" style={{fontSize:11,color:'var(--fg-3)',letterSpacing:'.14em'}}>{label||(value?'ENABLED':'OFF')}</span>
    </div>
  );
}

function App(){
  const [t,setTweak] = window.useTweaks({...StSS.SHARED_TWEAK_DEFAULTS});
  useEffect(()=>{StSS.applyTweaks(t,'green');},[t]);
  const [now,setNow] = useState(Date.now());
  useEffect(()=>{const id=setInterval(()=>setNow(Date.now()),1000); return ()=>clearInterval(id);},[]);

  const [tg, setTg] = useState(true);
  const [discord, setDiscord] = useState(true);
  const [email, setEmail] = useState(false);
  const [audio, setAudio] = useState(true);
  const [autoStart, setAutoStart] = useState(false);
  const [haptic, setHaptic] = useState(true);
  const [showKeys, setShowKeys] = useState(false);

  const TweaksPanel = window.TweaksPanel;

  return (
    <div className="page">
      <StSS.Topbar active="settings" now={now}/>
      <StSS.PageHead
        icon={<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" style={{color:'var(--accent)'}}/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" style={{color:'var(--accent)'}}/></svg>}
        title="Settings"
        subtitle="Account · API keys · notifications · appearance"
        accent="green"
        badges={<><StSS.Chip kind="green">● ACCOUNT VERIFIED</StSS.Chip><StSS.Chip>2FA · ON</StSS.Chip></>}
      />

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
        <Card title="Account">
          <Row label="Display Name"><input defaultValue="commander_07" className="mono" style={{width:'100%',padding:'8px 10px',background:'rgba(0,0,0,.5)',border:'1px solid var(--border-soft)',borderRadius:6,color:'var(--fg)',fontSize:12}}/></Row>
          <Row label="Email" hint="Account recovery"><input defaultValue="commander@signal.ops" className="mono" style={{width:'100%',padding:'8px 10px',background:'rgba(0,0,0,.5)',border:'1px solid var(--border-soft)',borderRadius:6,color:'var(--fg)',fontSize:12}}/></Row>
          <Row label="2FA" hint="TOTP via authenticator"><Toggle value={true} onChange={()=>{}} label="ENABLED · TOTP"/></Row>
          <Row label="Plan"><div><span className="chip chip-cyan">PRO</span> <span className="mono" style={{marginLeft:8,fontSize:10,color:'var(--fg-4)'}}>renews 2026-06-01</span></div></Row>
        </Card>

        <Card title="Notifications" hint="// where to ping you">
          <Row label="Telegram" hint="Trade alerts + summary"><Toggle value={tg} onChange={setTg}/></Row>
          <Row label="Discord" hint="#signals webhook"><Toggle value={discord} onChange={setDiscord}/></Row>
          <Row label="Email" hint="Daily digest"><Toggle value={email} onChange={setEmail}/></Row>
          <Row label="Audio Cue" hint="On signal arm + fill"><Toggle value={audio} onChange={setAudio}/></Row>
          <Row label="Haptic" hint="Mobile-only buzz on fills"><Toggle value={haptic} onChange={setHaptic}/></Row>
        </Card>

        <Card title="Exchange API Keys" hint="// live trading credentials">
          {['BINANCE','PHEMEX','BYBIT','BINGX'].map(ex=>(
            <Row key={ex} label={ex} hint={ex==='PHEMEX'?'Primary execution venue':null}>
              <div style={{display:'flex',gap:6,alignItems:'center'}}>
                <input type={showKeys?'text':'password'} defaultValue={`••••••${ex.slice(0,4)}_${Math.random().toString(36).slice(2,6)}`} className="mono" style={{flex:1,padding:'8px 10px',background:'rgba(0,0,0,.5)',border:'1px solid var(--border-soft)',borderRadius:6,color:'var(--fg)',fontSize:11}}/>
                <span className="chip chip-green">● LINKED</span>
              </div>
            </Row>
          ))}
          <div style={{padding:'12px 0 0',display:'flex',gap:8}}>
            <button className="btn" onClick={()=>setShowKeys(s=>!s)} style={{padding:'6px 12px',fontSize:10,letterSpacing:'.18em'}}>{showKeys?'◉ HIDE':'◯ SHOW'} KEYS</button>
            <button className="btn btn-cyan" style={{padding:'6px 12px',fontSize:10,letterSpacing:'.18em'}}>+ ADD EXCHANGE</button>
          </div>
        </Card>

        <Card title="Bot Behavior" hint="// global runtime defaults">
          <Row label="Auto-start on boot" hint="Resume bot after server restart"><Toggle value={autoStart} onChange={setAutoStart}/></Row>
          <Row label="Trading Mode"><div className="tab-switch" style={{display:'inline-flex'}}><button className="active">LIVE</button><button>PAPER</button></div></Row>
          <Row label="Default Leverage" hint="Override per-strategy"><input type="number" defaultValue="5" className="mono" style={{width:80,padding:'8px 10px',background:'rgba(0,0,0,.5)',border:'1px solid var(--border-soft)',borderRadius:6,color:'var(--fg)',fontSize:12}}/></Row>
          <Row label="Daily Kill Switch" hint="% drawdown stops bot"><input type="number" defaultValue="10" className="mono" style={{width:80,padding:'8px 10px',background:'rgba(0,0,0,.5)',border:'1px solid var(--red-border)',borderRadius:6,color:'var(--red-2)',fontSize:12,fontWeight:700}}/> <span className="mono" style={{color:'var(--fg-4)',fontSize:10,letterSpacing:'.18em'}}>%</span></Row>
        </Card>

        <Card title="Appearance" hint="// uses Tweaks panel for live preview">
          <Row label="Tactical Background"><Toggle value={t.tacticalBg} onChange={v=>setTweak('tacticalBg',v)}/></Row>
          <Row label="HUD Overlays"><Toggle value={t.hudOverlays} onChange={v=>setTweak('hudOverlays',v)}/></Row>
          <Row label="Density">
            <div className="tab-switch" style={{display:'inline-flex'}}>
              {['sparse','balanced','dense'].map(d=><button key={d} className={t.density===d?'active':''} onClick={()=>setTweak('density',d)}>{d.toUpperCase()}</button>)}
            </div>
          </Row>
        </Card>

        <Card title="Danger Zone" hint="// destructive actions">
          <Row label="Export all trade data" hint="CSV · JSON"><button className="btn" style={{padding:'8px 14px',fontSize:11}}>↓ EXPORT</button></Row>
          <Row label="Reset ML model" hint="Sends to Drills · Training Ground"><a href="Training.html#drills" className="btn" style={{padding:'8px 14px',fontSize:11,textDecoration:'none',display:'inline-block'}}>OPEN DRILLS →</a></Row>
          <Row label="Delete account" hint="Irreversible · removes all data"><button className="btn btn-red" style={{padding:'8px 14px',fontSize:11,fontWeight:700}}>⚠ DELETE ACCOUNT</button></Row>
        </Card>
      </div>

      <StSS.FooterStatus now={now}/>

      {TweaksPanel && <TweaksPanel title="Tweaks">
        <StSS.SharedTweaksControls t={t} setTweak={setTweak}/>
      </TweaksPanel>}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

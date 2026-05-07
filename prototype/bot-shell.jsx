// ── BOT — unified tabbed shell ──────────────────────────────
const BotSS = window.SS;
function BotShell(){
  const [tab, setTab] = useState(()=>{
    const h = (location.hash || '').replace('#','').toLowerCase();
    return (h==='status'||h==='setup') ? h : 'setup';
  });
  useEffect(()=>{ location.hash = tab; },[tab]);
  const [now, setNow] = useState(Date.now());
  useEffect(()=>{ const id=setInterval(()=>setNow(Date.now()),1000); return ()=>clearInterval(id); },[]);
  return (
    <div className="page">
      <BotSS.Topbar active="bot" now={now}/>
      <div className="bot-tab-banner">
        <div className="tab-switch">
          <button className={tab==='setup'?'active':''} onClick={()=>setTab('setup')}>◇ SETUP · pre-deploy</button>
          <button className={tab==='status'?'active':''} onClick={()=>setTab('status')}>● STATUS · live exchange</button>
        </div>
        <span className="mono" style={{fontSize:10,color:'var(--fg-3)',letterSpacing:'.18em'}}>
          {tab==='setup'?'// CONFIGURE → DEPLOY':'// LIVE · REAL FUNDS · IRREVERSIBLE'}
        </span>
      </div>
      <div style={{display: tab==='setup'?'block':'none'}}><window.SetupApp/></div>
      <div style={{display: tab==='status'?'block':'none'}}><window.StatusApp/></div>
    </div>
  );
}
function bootBot(){
  if (window.SetupApp && window.StatusApp) {
    ReactDOM.createRoot(document.getElementById('root')).render(<BotShell/>);
  } else { setTimeout(bootBot, 30); }
}
bootBot();

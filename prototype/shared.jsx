// ── SniperSight shared chrome ─────────────────────────────────
// Loaded into every page; exposes globals on window.SS_*

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ── Tactical Background controller ──────────────────────────
function applyTweaks(t, pageAccent){
  const root = document.documentElement;
  // page accent override wins unless tweak forces a theme
  const accents = {
    green: { c:'#00ffaa', bg:'rgba(0,255,170,.10)', bd:'rgba(0,255,170,.30)' },
    amber: { c:'#fbbf24', bg:'rgba(251,191,36,.10)', bd:'rgba(251,191,36,.35)' },
    blue:  { c:'#60a5fa', bg:'rgba(96,165,250,.10)', bd:'rgba(96,165,250,.30)' },
    cyan:  { c:'#22d3ee', bg:'rgba(34,211,238,.10)',  bd:'rgba(34,211,238,.30)' },
    purple:{ c:'#c084fc', bg:'rgba(192,132,252,.10)', bd:'rgba(192,132,252,.30)' },
    red:   { c:'#f87171', bg:'rgba(248,113,113,.10)', bd:'rgba(248,113,113,.35)' },
  };
  const themeKey = (t.theme === 'page') ? pageAccent : t.theme;
  const a = accents[themeKey] || accents[pageAccent] || accents.green;
  root.style.setProperty('--accent', a.c);
  root.style.setProperty('--accent-bg', a.bg);
  root.style.setProperty('--accent-border', a.bd);

  const bg = document.getElementById('tactical-bg');
  if (bg) bg.classList.toggle('off', !t.tacticalBg);

  document.body.classList.toggle('hud-overlays-off', !t.hudOverlays);

  document.body.classList.remove('density-sparse','density-balanced','density-dense');
  document.body.classList.add('density-' + (t.density || 'balanced'));
}

// ── Formatters ──────────────────────────────────────────────
function fmtMoney(v, d){ d = d == null ? 2 : d; return (v<0?'-$':'$') + Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}); }
function fmtPct(v, d){ d = d == null ? 2 : d; return (v>=0?'+':'') + v.toFixed(d) + '%'; }
function fmtPrice(p){ if(p<1) return '$'+p.toFixed(5); if(p<100) return '$'+p.toFixed(4); return '$'+p.toFixed(2); }
function fmtDur(seconds){
  if (seconds<60) return seconds+'s';
  if (seconds<3600) return Math.floor(seconds/60)+'m '+(seconds%60)+'s';
  const h=Math.floor(seconds/3600), m=Math.floor((seconds%3600)/60);
  return h+'h '+m+'m';
}
function fmtNum(v){
  if (Math.abs(v) >= 1e9) return (v/1e9).toFixed(2)+'B';
  if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(2)+'M';
  if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(2)+'K';
  return v.toFixed(2);
}

// ── Reticle SVG (top-right corner of accent panels) ─────────
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

// ── Topbar / Page head / Footer ─────────────────────────────
function Topbar({ active, now }){
  const links = [
    { id:'intel',   label:'Intel',    href:'Intel.html' },
    { id:'scanner', label:'Scanner',  href:'Scanner.html' },
    { id:'bot',     label:'Bot',      href:'Bot.html' },
    { id:'training',label:'Training', href:'Training.html' },
    { id:'settings',label:'Risk',     href:'Settings.html' },
  ];
  return (
    <div className="topbar">
      <a href="Landing.html" className="brand" style={{textDecoration:'none',color:'inherit'}}>
        <img src="logo.png" alt="SniperSight" style={{height:34,width:'auto',display:'block',filter:'drop-shadow(0 0 12px rgba(0,255,170,.25))'}}/>
      </a>
      <nav className="nav">
        {links.map(l => (
          <a key={l.id} href={l.href} className={active===l.id?'active':''}>{l.label}</a>
        ))}
      </nav>
      <div style={{display:'flex',alignItems:'center',gap:10}}>
        <span className="chip chip-green">● ONLINE</span>
        <span className="chip">UTC {new Date(now).toUTCString().slice(17,25)}</span>
      </div>
    </div>
  );
}

function PageHead({ icon, title, subtitle, badges, accent }){
  return (
    <div className="page-head">
      <div className="page-title">
        <div className="icon">{icon}</div>
        <div>
          <h1 style={accent==='red'?{}:{}} className={accent==='red'?'live':''}>{title}</h1>
          <div className="sub">{subtitle}</div>
        </div>
      </div>
      <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
        {badges}
      </div>
    </div>
  );
}

function FooterStatus({ now, latency }){
  return (
    <div style={{marginTop:24,padding:'12px 18px',border:'1px solid var(--border-soft)',borderRadius:10,background:'rgba(0,0,0,.3)',display:'flex',alignItems:'center',justifyContent:'space-between',gap:14,flexWrap:'wrap'}}>
      <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
        <span className="chip chip-green">● BINANCE WS</span>
        <span className="chip chip-green">● PHEMEX REST</span>
        <span className="chip chip-green">● TELEGRAM</span>
        <span className="chip">● BACKEND {latency || 41}ms</span>
      </div>
      <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>build 1.0.0+5cdb504 · {new Date(now).toISOString().slice(0,19).replace('T',' ')}Z</div>
    </div>
  );
}

// ── Mini metric tile ────────────────────────────────────────
function Mini({ label, value, accent, bold, valueColor }){
  return (
    <div>
      <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase',marginBottom:4}}>{label}</div>
      <div className="mono" style={{fontSize:13,fontWeight: bold?800:600, color: valueColor || (accent?'var(--accent)':'var(--fg)')}}>{value}</div>
    </div>
  );
}

// ── SectionHead w/ pulsing dot ──────────────────────────────
function SectionHead({ title, right }){
  return (
    <div className="sec-head">
      <div className="sec-title"><span className="dot"/> {title}</div>
      {right}
    </div>
  );
}

// ── RiskBar (small horizontal limit bar) ────────────────────
function RiskBar({ label, value, max, unit, color }){
  const pct = Math.min(100, (value/max)*100);
  const c = color || 'var(--green-soft)';
  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
        <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em',textTransform:'uppercase'}}>{label}</span>
        <span className="mono" style={{fontSize:11,color:c,fontWeight:700}}>{value}{unit||''} <span style={{color:'var(--fg-4)'}}>/ {max}{unit||''}</span></span>
      </div>
      <div style={{position:'relative',height:6,borderRadius:3,background:'rgba(0,0,0,.5)',overflow:'hidden',border:'1px solid var(--border-soft)'}}>
        <div style={{height:'100%',width:pct+'%',background:`linear-gradient(90deg, ${c}, color-mix(in oklch, ${c} 60%, transparent))`,boxShadow:`0 0 10px ${c}`,transition:'width .6s ease'}}/>
      </div>
    </div>
  );
}

// ── Pill / Chip helpers ─────────────────────────────────────
function Chip({ kind, children, style }){
  const cls = 'chip ' + (kind ? 'chip-'+kind : '');
  return <span className={cls} style={style}>{children}</span>;
}

// ── Modal shell ─────────────────────────────────────────────
function Modal({ onClose, children, maxWidth }){
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" style={{maxWidth: maxWidth||620}} onClick={e=>e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

// ── Default tweaks shared across all pages ──────────────────
const SHARED_TWEAK_DEFAULTS = {
  theme: 'page',           // 'page' = use the page's own accent; or override green/amber/blue
  density: 'balanced',
  tacticalBg: true,
  hudOverlays: true,
  simSpeed: 1,
};

// ── Shared TweaksPanel helper (pages add page-specific bits) ─
function SharedTweaksControls({ t, setTweak }){
  return (
    <window.TweakSection title="Theme">
      <window.TweakRadio label="Accent" value={t.theme} onChange={v=>setTweak('theme',v)} options={[
        {label:'Page', value:'page'},
        {label:'Green',value:'green'},
        {label:'Amber',value:'amber'},
        {label:'Blue', value:'blue'},
      ]}/>
      <window.TweakRadio label="Density" value={t.density} onChange={v=>setTweak('density',v)} options={[
        {label:'Sparse',  value:'sparse'},
        {label:'Balanced',value:'balanced'},
        {label:'Dense',   value:'dense'},
      ]}/>
      <window.TweakToggle label="Tactical Background" value={t.tacticalBg} onChange={v=>setTweak('tacticalBg',v)} hint="Scanlines, grid, drift glow"/>
      <window.TweakToggle label="HUD Overlays" value={t.hudOverlays} onChange={v=>setTweak('hudOverlays',v)} hint="Reticles, brackets, scanline texture"/>
      <window.TweakSlider label="Sim Speed" value={t.simSpeed} min={0.5} max={4} step={0.5} onChange={v=>setTweak('simSpeed',v)}/>
    </window.TweakSection>
  );
}

// ── Tactical background DOM (rendered once per page) ────────
function TacticalBgDom(){
  // Used by pages that prefer to mount via React rather than static HTML.
  return (
    <div className="tactical-bg" id="tactical-bg">
      <div className="glow"></div>
      <div className="grid"></div>
      <div className="grain"></div>
      <div className="scanline"></div>
    </div>
  );
}

// Expose all helpers globally so each page's app script can use them
Object.assign(window, {
  SS: {
    applyTweaks, fmtMoney, fmtPct, fmtPrice, fmtDur, fmtNum,
    Reticle, Topbar, PageHead, FooterStatus, Mini, SectionHead,
    RiskBar, Chip, Modal, SharedTweaksControls, TacticalBgDom,
    SHARED_TWEAK_DEFAULTS,
  },
});

// ── Scanner Mode Picker ─────────────────────────────────────
// 4 detection presets: OVERWATCH / STRIKE / SURGICAL / STEALTH (default)
// Plus an AI-Recommendation hero that suggests one based on regime.

const SCANNER_MODES = [
  {
    id: 'overwatch',
    name: 'OVERWATCH',
    tagline: 'Macro Surveillance',
    desc: 'Swing trades · days–weeks · A+ macro setups only',
    timeframes: ['1W','1D','4H','1H','15m','5m'],
    critical: ['1W','1D'],
    primary: '4H',
    minScore: 72,
    minRR: 2.0,
    types: ['SWING'],
    detection: 'LuxAlgo · strict',
    bestFor: 'Patient swing traders waiting for weekly + daily structure alignment.',
    accent: 'cyan',
    feel: 'premium',
    bullets: [
      'Requires 1W + 1D structure alignment',
      'Enforces 2:1 R:R minimum',
      'Filters for institutional accumulation zones',
    ],
  },
  {
    id: 'strike',
    name: 'STRIKE',
    tagline: 'Intraday Aggressive',
    desc: 'Hours · momentum + trend continuation · highest signal volume',
    timeframes: ['4H','1H','15m','5m'],
    critical: ['15m'],
    primary: '15m',
    minScore: 68,
    minRR: 1.2,
    types: ['SWING','INTRADAY','SCALP'],
    detection: 'LuxAlgo · aggressive',
    bestFor: 'Active traders who want maximum signal flow on momentum plays.',
    accent: 'amber',
    feel: 'fast',
    bullets: [
      'Loose detection · maximum signals',
      '15m is the critical timeframe',
      'Fast decisions on trend continuation',
    ],
  },
  {
    id: 'surgical',
    name: 'SURGICAL',
    tagline: 'Precision',
    desc: 'Minutes–hours · scalp + intraday · controlled risk only',
    timeframes: ['4H','1H','15m','5m'],
    critical: ['15m'],
    primary: '15m',
    minScore: 70,
    minRR: 1.5,
    types: ['INTRADAY','SCALP'],
    detection: 'LuxAlgo · strict',
    bestFor: 'Experienced traders who want fewer, cleaner setups with tight stops.',
    accent: 'red',
    feel: 'tight',
    bullets: [
      'Strict detection · quality over quantity',
      'No swing setups — intraday + scalp only',
      'Tight stops · controlled risk',
    ],
  },
  {
    id: 'stealth',
    name: 'STEALTH',
    tagline: 'Balanced · Default',
    desc: 'Hours–days · cascades swing → intraday → scalp · all-around',
    timeframes: ['1D','4H','1H','15m','5m'],
    critical: ['4H','1H'],
    primary: '1H',
    minScore: 70,
    minRR: 1.5,
    types: ['SWING','INTRADAY','SCALP'],
    detection: 'Defaults · balanced',
    bestFor: 'All-around trading — solid signal volume with good quality. System default.',
    accent: 'green',
    feel: 'default',
    bullets: [
      'Cascades swing → intraday → scalp · picks best',
      '4H + 1H critical timeframes',
      'System default · pure detection',
    ],
  },
];

const ACCENT_HEX = {
  green: '#4ade80', amber: '#fbbf24', cyan: '#22d3ee', red: '#f87171',
};

function ModeIcon({ id, color }){
  // distinct icon per mode, all monochromatic line-art
  const s = { stroke:color, strokeWidth:1.5, fill:'none', strokeLinecap:'round', strokeLinejoin:'round' };
  if (id==='overwatch') return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...s}>
      <circle cx="12" cy="12" r="9"/>
      <circle cx="12" cy="12" r="5"/>
      <circle cx="12" cy="12" r="1.5" fill={color}/>
      <path d="M12 1 V4 M12 20 V23 M1 12 H4 M20 12 H23"/>
    </svg>
  );
  if (id==='strike') return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...s}>
      <path d="M13 2 L4 14 L11 14 L9 22 L20 9 L13 9 Z" fill={color} fillOpacity=".15"/>
    </svg>
  );
  if (id==='surgical') return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...s}>
      <path d="M3 21 L13 11 L17 7 L21 3 L21 7 L17 7 M13 11 L17 15"/>
      <circle cx="6" cy="18" r="2"/>
    </svg>
  );
  if (id==='stealth') return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...s}>
      <path d="M12 3 L12 9 M9 6 L15 6"/>
      <path d="M3 14 Q12 8 21 14 Q12 20 3 14 Z"/>
      <circle cx="12" cy="14" r="2.5" fill={color} fillOpacity=".4"/>
    </svg>
  );
  return null;
}

// Mini gauge for score (0–100)
function ScoreGauge({ value, color, size=44 }){
  const r = size/2 - 4;
  const C = 2*Math.PI*r;
  const dash = (value/100)*C;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,.06)" strokeWidth="3" fill="none"/>
      <circle cx={size/2} cy={size/2} r={r} stroke={color} strokeWidth="3" fill="none"
        strokeDasharray={`${dash} ${C}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{filter:`drop-shadow(0 0 4px ${color})`}}/>
      <text x="50%" y="54%" textAnchor="middle" fill={color} fontFamily="Share Tech Mono, monospace" fontSize="11" fontWeight="700">{value}</text>
    </svg>
  );
}

// Background regime — drives the AI recommendation
function pickRecommendation(){
  // For now, default per spec: STEALTH unless macro is "loaded"
  // We pick OVERWATCH ~25% of the time to demo the regime override
  const r = (typeof window !== 'undefined' && window.__SCANNER_REGIME__) || (Math.random() < 0.25 ? 'macro' : 'balanced');
  if (r === 'macro') {
    return {
      mode: 'overwatch',
      reason: 'Weekly + Daily structure aligned · BTC dominance compressing · macro accumulation signature detected',
      confidence: 'HIGH',
      regime: 'MACRO · LOADED',
    };
  }
  return {
    mode: 'stealth',
    reason: 'Balanced regime · mixed signals across HTF · system default in effect',
    confidence: 'MED',
    regime: 'BALANCED',
  };
}

// ── Hero recommendation block ───────────────────────────────
function ScannerRecommendationHero({ rec, currentMode, onActivate }){
  const mode = SCANNER_MODES.find(m => m.id === rec.mode);
  const color = ACCENT_HEX[mode.accent];
  const isActive = currentMode === rec.mode;
  return (
    <section className="panel panel-accent" style={{marginBottom:18,position:'relative',overflow:'hidden'}}>
      <div style={{
        position:'absolute', inset:0,
        background:`radial-gradient(ellipse 60% 80% at 70% 50%, ${color}18, transparent 60%)`,
        pointerEvents:'none',
      }}/>
      <SS.Reticle/>
      <div className="corner-tag tl">// AI-ADVISORY</div>
      <div className="corner-tag tr" style={{color}}>{rec.regime}</div>
      <div style={{padding:'24px 26px',position:'relative'}}>
        <div style={{display:'grid',gridTemplateColumns:'1fr auto',gap:24,alignItems:'center'}}>
          <div>
            <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10}}>
              <span style={{
                display:'inline-flex',alignItems:'center',gap:6,
                fontFamily:'JetBrains Mono,monospace',fontSize:9.5,letterSpacing:'.22em',
                color, textTransform:'uppercase', padding:'3px 10px',
                border:`1px solid ${color}55`, background:`${color}11`, borderRadius:99,
              }}>
                <span style={{width:5,height:5,borderRadius:'50%',background:color,boxShadow:`0 0 8px ${color}`,animation:'pulse 1.6s ease-in-out infinite'}}/>
                AI ADVISORY · {rec.confidence} CONVICTION
              </span>
              <span className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.18em'}}>RECOMMENDED MODE</span>
            </div>
            <div style={{display:'flex',alignItems:'baseline',gap:14,marginBottom:8,flexWrap:'wrap'}}>
              <h2 style={{
                margin:0,fontFamily:'Share Tech Mono,monospace',fontSize:54,letterSpacing:'.04em',
                color, textShadow:`0 0 18px ${color}66, 0 0 36px ${color}33`,lineHeight:.95,
              }}>{mode.name}</h2>
              <span className="mono" style={{fontSize:13,color:'var(--fg-2)',letterSpacing:'.12em',textTransform:'uppercase'}}>{mode.tagline}</span>
            </div>
            <p style={{
              margin:'6px 0 14px',maxWidth:680,
              fontSize:14,lineHeight:1.55,color:'var(--fg-2)',
              borderLeft:`2px solid ${color}66`,paddingLeft:12,fontStyle:'italic',
            }}>"{rec.reason}"</p>
            {isActive ? (
              <div style={{
                display:'inline-flex',alignItems:'center',gap:10,padding:'10px 18px',
                border:`1.5px solid ${color}`,background:`${color}14`,borderRadius:8,
                fontFamily:'Share Tech Mono,monospace',fontSize:13,letterSpacing:'.22em',color,textTransform:'uppercase',
              }}>
                ✓ Protocol Active
              </div>
            ) : (
              <button onClick={()=>onActivate(rec.mode)} style={{
                display:'inline-flex',alignItems:'center',gap:10,padding:'12px 22px',
                border:'none',background:color,color:'#0a0a0a',borderRadius:8,cursor:'pointer',
                fontFamily:'Share Tech Mono,monospace',fontSize:13,letterSpacing:'.22em',fontWeight:800,textTransform:'uppercase',
                boxShadow:`0 0 0 1px ${color}, 0 0 24px ${color}66`,
                transition:'transform .12s, box-shadow .15s',
              }}
              onMouseEnter={e=>{e.currentTarget.style.transform='translateY(-1px)';e.currentTarget.style.boxShadow=`0 0 0 1px ${color}, 0 0 36px ${color}99`;}}
              onMouseLeave={e=>{e.currentTarget.style.transform='';e.currentTarget.style.boxShadow=`0 0 0 1px ${color}, 0 0 24px ${color}66`;}}
              >
                ⌬ ACTIVATE {mode.name}
              </button>
            )}
          </div>
          <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:8}}>
            <ScoreGauge value={mode.minScore} color={color} size={86}/>
            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.20em'}}>MIN SCORE</div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Mode card ──────────────────────────────────────────────
function ModeCard({ mode, selected, recommended, onSelect }){
  const color = ACCENT_HEX[mode.accent];
  return (
    <button
      type="button"
      onClick={()=>onSelect(mode.id)}
      style={{
        position:'relative', textAlign:'left',
        padding:'16px 16px 14px',
        background: selected ? `linear-gradient(180deg, ${color}18, ${color}06)` : 'rgba(0,0,0,.40)',
        border: `1.5px solid ${selected ? color : 'var(--border-soft)'}`,
        borderRadius:10, cursor:'pointer',
        transition:'all .15s',
        color:'var(--fg)', fontFamily:'inherit',
        boxShadow: selected ? `0 0 0 1px ${color}, 0 0 22px ${color}33, inset 0 0 30px ${color}10` : 'none',
        display:'flex', flexDirection:'column', gap:10,
        minHeight:200,
      }}
      onMouseEnter={e=>{ if(!selected) e.currentTarget.style.borderColor = `${color}88`; }}
      onMouseLeave={e=>{ if(!selected) e.currentTarget.style.borderColor = 'var(--border-soft)'; }}
    >
      {recommended && (
        <span style={{
          position:'absolute', top:-9, right:14, padding:'2px 8px',
          background:'#0a0a0a', border:`1px solid ${color}`, color, borderRadius:4,
          fontFamily:'JetBrains Mono,monospace', fontSize:8.5, letterSpacing:'.22em', fontWeight:700,
        }}>★ RECOMMENDED</span>
      )}
      {selected && (
        <span style={{
          position:'absolute', top:10, right:10,
          fontFamily:'JetBrains Mono,monospace', fontSize:8.5, letterSpacing:'.22em', fontWeight:700,
          color, padding:'2px 6px', border:`1px solid ${color}`, borderRadius:3,
        }}>● ACTIVE</span>
      )}

      {/* header */}
      <div style={{display:'flex',alignItems:'center',gap:10}}>
        <div style={{
          width:34,height:34,display:'grid',placeItems:'center',
          border:`1px solid ${color}55`,background:`${color}10`,borderRadius:8,
        }}>
          <ModeIcon id={mode.id} color={color}/>
        </div>
        <div>
          <div style={{
            fontFamily:'Share Tech Mono,monospace',fontSize:18,letterSpacing:'.14em',
            color:selected?color:'var(--fg)', textShadow:selected?`0 0 10px ${color}55`:'none',
          }}>{mode.name}</div>
          <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.16em',textTransform:'uppercase',marginTop:2}}>{mode.tagline}</div>
        </div>
      </div>

      {/* desc */}
      <div style={{fontSize:11.5,color:'var(--fg-3)',lineHeight:1.45,minHeight:32}}>{mode.desc}</div>

      {/* metric strip */}
      <div style={{display:'grid',gridTemplateColumns:'auto 1fr 1fr',gap:10,alignItems:'center',padding:'8px 0',borderTop:'1px dashed var(--border-soft)',borderBottom:'1px dashed var(--border-soft)'}}>
        <ScoreGauge value={mode.minScore} color={color} size={40}/>
        <div>
          <div className="mono" style={{fontSize:8.5,color:'var(--fg-4)',letterSpacing:'.18em'}}>MIN R:R</div>
          <div className="mono" style={{fontSize:14,color,fontWeight:700}}>{mode.minRR.toFixed(1)}</div>
        </div>
        <div>
          <div className="mono" style={{fontSize:8.5,color:'var(--fg-4)',letterSpacing:'.18em'}}>PRIMARY</div>
          <div className="mono" style={{fontSize:14,color:'var(--fg)',fontWeight:700}}>{mode.primary}</div>
        </div>
      </div>

      {/* trade types */}
      <div style={{display:'flex',gap:5,flexWrap:'wrap'}}>
        {mode.types.map(t => (
          <span key={t} className="chip" style={{fontSize:8.5,color,borderColor:`${color}55`,background:`${color}10`,padding:'2px 7px'}}>{t}</span>
        ))}
      </div>

      {/* critical TFs */}
      <div style={{marginTop:'auto'}}>
        <div className="mono" style={{fontSize:8.5,color:'var(--fg-4)',letterSpacing:'.18em',marginBottom:4}}>CRITICAL · REJECTS IF MISSING</div>
        <div style={{display:'flex',gap:4,flexWrap:'wrap'}}>
          {mode.timeframes.map(tf => {
            const isCritical = mode.critical.includes(tf);
            return (
              <span key={tf} className="mono" style={{
                fontSize:9.5, padding:'2px 6px', borderRadius:3,
                color: isCritical ? color : 'var(--fg-4)',
                background: isCritical ? `${color}14` : 'transparent',
                border:`1px solid ${isCritical ? color+'66' : 'var(--border-soft)'}`,
                fontWeight: isCritical ? 700 : 500,
                letterSpacing:'.06em',
              }}>{tf}{isCritical?' ●':''}</span>
            );
          })}
        </div>
      </div>
    </button>
  );
}

// ── Wrapper section ────────────────────────────────────────
function ScannerModePicker({ mode, setMode, recommendation }){
  return (
    <div style={{marginBottom:18}}>
      <ScannerRecommendationHero rec={recommendation} currentMode={mode} onActivate={setMode}/>
      <section className="panel" style={{position:'relative'}}>
        <SS.SectionHead
          title="Detection Modes"
          right={<>
            <SS.Chip kind="accent">{SCANNER_MODES.find(m=>m.id===mode)?.name || ''}</SS.Chip>
            <SS.Chip>SIGNAL CONFIG</SS.Chip>
          </>}
        />
        <div className="corner-tag tl">// MODE-SELECT</div>
        <div className="corner-tag tr">4 PROFILES</div>
        <div style={{padding:'18px 18px 14px'}}>
          <div className="mono" style={{fontSize:10,color:'var(--fg-4)',letterSpacing:'.20em',textTransform:'uppercase',marginBottom:14}}>// SCANNER · WHICH SIGNALS GET SURFACED TO THE BOT</div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(4, 1fr)',gap:12}} className="mode-grid">
            {SCANNER_MODES.map(m => (
              <ModeCard
                key={m.id}
                mode={m}
                selected={mode === m.id}
                recommended={recommendation.mode === m.id}
                onSelect={setMode}
              />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

Object.assign(window, {
  SCANNER_MODES, ScannerModePicker, pickRecommendation,
});

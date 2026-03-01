// @ts-nocheck
import { useState, useEffect, useRef } from "react";

const FONTS = `@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;400;500;600;700&family=Share+Tech+Mono&family=Bebas+Neue&display=swap');`;

// ─── Simulated live data ───────────────────────────────────────────────────
const useLiveData = () => {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 2000);
    return () => clearInterval(id);
  }, []);

  const jitter = (base, pct = 0.003) => +(base * (1 + (Math.random() - 0.5) * pct)).toFixed(2);

  return {
    tick,
    btc:    { price: jitter(83420), change: -2.34, volume: "28.4B", dominance: jitter(52.6, 0.001) },
    eth:    { price: jitter(2184),  change: -3.12, volume: "12.1B", dominance: jitter(12.1, 0.001) },
    sol:    { price: jitter(134.2), change: +1.44, volume: "4.2B"  },
    bnb:    { price: jitter(598.1), change: -0.88, volume: "1.8B"  },
    btcDom: jitter(52.6, 0.001),
    ethDom: jitter(12.1, 0.001),
    usdtDom:jitter(5.8,  0.001),
    fearGreed: 28,
    regime: "DISTRIBUTION",
    cycleDay: 312,
    cyclePct: 72,
    fundingBtc: -0.014,
    fundingEth: -0.021,
    oiBtc: "18.2B",
    oiEth: "9.4B",
    signals: [
      { time: "14:32", asset: "BTC/USDT", type: "ORDER BLOCK", tf: "4H", score: 87, dir: "SHORT" },
      { time: "14:18", asset: "ETH/USDT", type: "FVG FILL",    tf: "1H", score: 79, dir: "SHORT" },
      { time: "13:55", asset: "SOL/USDT", type: "BOS",         tf: "15M",score: 64, dir: "LONG"  },
      { time: "13:41", asset: "BNB/USDT", type: "CHOCH",       tf: "4H", score: 81, dir: "SHORT" },
      { time: "13:20", asset: "AVAX/USDT",type: "OB+FVG",      tf: "1H", score: 91, dir: "SHORT" },
    ],
    narratives: [
      { name: "AI Agents",  strength: 82, trend: "↑", sector: "hot"  },
      { name: "RWA",        strength: 61, trend: "↑", sector: "warm" },
      { name: "DePIN",      strength: 54, trend: "→", sector: "warm" },
      { name: "L2 Scaling", strength: 38, trend: "↓", sector: "cold" },
      { name: "Meme Coins", strength: 22, trend: "↓", sector: "cold" },
      { name: "Gaming Fi",  strength: 18, trend: "↓", sector: "cold" },
    ],
    liquidityLevels: [
      { label: "MAJOR RESISTANCE", price: "89,200", type: "sell" },
      { label: "WEEKLY HIGH LIQ",  price: "87,500", type: "sell" },
      { label: "4H ORDER BLOCK",   price: "84,100", type: "sell" },
      { label: "▶ CURRENT PRICE",  price: "83,420", type: "current" },
      { label: "4H SUPPORT OB",    price: "81,800", type: "buy"  },
      { label: "DAILY DEMAND",     price: "79,200", type: "buy"  },
      { label: "MAJOR SUPPORT",    price: "74,000", type: "buy"  },
    ],
  };
};

// ─── Sub-components ────────────────────────────────────────────────────────

const ScanLine = () => (
  <div style={{
    position:"fixed", top:0, left:0, right:0, bottom:0,
    pointerEvents:"none", zIndex:9999,
    background:"repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,200,0.012) 2px, rgba(0,255,200,0.012) 4px)",
  }} />
);

const Glitch = ({ text }) => {
  const [glitch, setGlitch] = useState(false);
  useEffect(() => {
    const id = setInterval(() => { setGlitch(true); setTimeout(() => setGlitch(false), 80); }, 6000);
    return () => clearInterval(id);
  }, []);
  return (
    <span style={{ position:"relative", display:"inline-block" }}>
      {glitch && <span style={{ position:"absolute", left:"2px", top:0, color:"#ff0040", opacity:0.7, clipPath:"inset(30% 0 50% 0)" }}>{text}</span>}
      {glitch && <span style={{ position:"absolute", left:"-2px", top:0, color:"#00ffff", opacity:0.7, clipPath:"inset(60% 0 10% 0)" }}>{text}</span>}
      {text}
    </span>
  );
};

const PulsingDot = ({ color = "#00ff88" }) => (
  <span style={{ display:"inline-block", width:8, height:8, borderRadius:"50%", background:color,
    boxShadow:`0 0 6px ${color}`, animation:"pulse 1.5s ease-in-out infinite" }} />
);

const MiniSparkline = ({ positive }) => {
  const pts = Array.from({length:20}, (_,i) => {
    const base = 50 + (positive ? i * 1.2 : -i * 1.2);
    return base + (Math.random()-0.5)*12;
  });
  const min = Math.min(...pts), max = Math.max(...pts);
  const norm = pts.map(p => 40 - ((p-min)/(max-min))*36);
  const d = norm.map((y,i) => `${i===0?"M":"L"}${i*3.5},${y}`).join(" ");
  const color = positive ? "#00ff88" : "#ff4466";
  return (
    <svg width="70" height="42" style={{ overflow:"visible" }}>
      <defs>
        <linearGradient id={`sg-${positive}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={d + ` L${19*3.5},42 L0,42 Z`} fill={`url(#sg-${positive})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
};

const RegimeBadge = ({ regime }) => {
  const map = {
    ACCUMULATION: { color:"#00aaff", bg:"rgba(0,170,255,0.1)", border:"rgba(0,170,255,0.4)" },
    MARKUP:       { color:"#00ff88", bg:"rgba(0,255,136,0.1)", border:"rgba(0,255,136,0.4)" },
    DISTRIBUTION: { color:"#ff6b00", bg:"rgba(255,107,0,0.1)", border:"rgba(255,107,0,0.4)" },
    MARKDOWN:     { color:"#ff4466", bg:"rgba(255,68,102,0.1)", border:"rgba(255,68,102,0.4)" },
  };
  const s = map[regime] || map.DISTRIBUTION;
  return (
    <div style={{ display:"inline-flex", alignItems:"center", gap:8, padding:"6px 14px",
      background:s.bg, border:`1px solid ${s.border}`, borderRadius:3,
      color:s.color, fontFamily:"'Share Tech Mono', monospace", fontSize:11, letterSpacing:3,
      textTransform:"uppercase", boxShadow:`0 0 12px ${s.border}` }}>
      <PulsingDot color={s.color} />
      {regime}
    </div>
  );
};

const FearGreedGauge = ({ value }) => {
  const angle = (value / 100) * 180 - 90;
  const label = value < 25 ? "EXTREME FEAR" : value < 45 ? "FEAR" : value < 55 ? "NEUTRAL" : value < 75 ? "GREED" : "EXTREME GREED";
  const color = value < 25 ? "#ff4466" : value < 45 ? "#ff8800" : value < 55 ? "#ffcc00" : value < 75 ? "#88ff44" : "#00ff88";
  const r = 60, cx = 75, cy = 70;
  const toXY = (deg) => {
    const rad = (deg - 90) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const arcPath = (start, end, radius) => {
    const s = toXY(start + (start === -90 ? 0.01 : 0));
    const e = toXY(end);
    const la = end - start > 180 ? 1 : 0;
    const r2 = radius;
    const cx2 = cx, cy2 = cy;
    const toXY2 = (deg) => {
      const rad = (deg - 90) * Math.PI / 180;
      return { x: cx2 + r2 * Math.cos(rad), y: cy2 + r2 * Math.sin(rad) };
    };
    const s2 = toXY2(start), e2 = toXY2(end);
    return `M ${s2.x} ${s2.y} A ${r2} ${r2} 0 ${la} 1 ${e2.x} ${e2.y}`;
  };
  const needleEnd = toXY(angle);
  return (
    <div style={{ textAlign:"center" }}>
      <svg width="150" height="90" style={{ overflow:"visible" }}>
        {[[-90,90,"rgba(255,68,102,0.6)"],[-90,-18,"rgba(255,136,0,0.6)"],
          [-18,18,"rgba(255,204,0,0.6)"],[18,54,"rgba(136,255,68,0.6)"],[54,90,"rgba(0,255,136,0.6)"]
        ].map(([s,e,c],i) => (
          <path key={i} d={arcPath(s,e,r)} fill="none" stroke={c} strokeWidth="8" strokeLinecap="round" />
        ))}
        <line x1={cx} y1={cy} x2={needleEnd.x} y2={needleEnd.y} stroke="#fff" strokeWidth="2" strokeLinecap="round"
          style={{ transition:"all 1s ease", transformOrigin:`${cx}px ${cy}px` }} />
        <circle cx={cx} cy={cy} r="5" fill="#fff" />
        <text x={cx} y={cy-14} textAnchor="middle" fill={color} fontSize="20"
          style={{ fontFamily:"'Bebas Neue', cursive", letterSpacing:1 }}>{value}</text>
      </svg>
      <div style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:10, letterSpacing:2, color, marginTop:-8 }}>{label}</div>
    </div>
  );
};

const CycleBar = ({ pct, day }) => (
  <div style={{ padding:"12px 0" }}>
    <div style={{ display:"flex", justifyContent:"space-between", marginBottom:6,
      fontFamily:"'Share Tech Mono', monospace", fontSize:10, color:"rgba(255,255,255,0.5)", letterSpacing:1 }}>
      <span>CYCLE DAY {day} / 365</span>
      <span>{pct}% COMPLETE</span>
    </div>
    <div style={{ height:6, background:"rgba(255,255,255,0.08)", borderRadius:3, overflow:"hidden" }}>
      <div style={{ height:"100%", width:`${pct}%`, borderRadius:3,
        background:"linear-gradient(90deg, #00ff88, #ffcc00, #ff6b00)",
        boxShadow:"0 0 10px rgba(255,107,0,0.4)", transition:"width 1s ease" }} />
    </div>
    <div style={{ display:"flex", justifyContent:"space-between", marginTop:6,
      fontFamily:"'Share Tech Mono', monospace", fontSize:9, color:"rgba(255,255,255,0.3)" }}>
      <span>◀ ACCUMULATION</span><span>MARKUP</span><span>DISTRIBUTION ▶</span>
    </div>
  </div>
);

// ─── Main Component ────────────────────────────────────────────────────────

export function Intel() {
  const data = useLiveData();
  const [activeTab, setActiveTab] = useState("overview");
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const fmt = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2 });
  const fmtDom = (n) => `${n.toFixed(1)}%`;

  const tabs = ["OVERVIEW", "STRUCTURE", "FLOW", "SIGNALS", "NARRATIVES"];

  const C = {
    bg:       "#080c18",
    surface:  "#0d1225",
    surfaceH: "#111830",
    border:   "rgba(0,200,180,0.12)",
    borderB:  "rgba(0,200,180,0.25)",
    accent:   "#00e5cc",
    green:    "#00ff88",
    red:      "#ff4466",
    orange:   "#ff6b00",
    yellow:   "#ffcc00",
    muted:    "rgba(255,255,255,0.35)",
    text:     "rgba(255,255,255,0.85)",
    mono:     "'Share Tech Mono', monospace",
    head:     "'Bebas Neue', cursive",
    body:     "'Rajdhani', sans-serif",
  };

  const card = (extra = {}) => ({
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 4,
    padding: "20px 22px",
    position: "relative",
    overflow: "hidden",
    ...extra,
  });

  const label = (text, extra = {}) => (
    <div style={{ fontFamily: C.mono, fontSize: 9, letterSpacing: 3,
      color: C.muted, textTransform:"uppercase", marginBottom: 6, ...extra }}>{text}</div>
  );

  const signalColor = (dir) => dir === "LONG" ? C.green : C.red;

  return (
    <div style={{ background: C.bg, minHeight:"100vh", color: C.text, fontFamily: C.body,
      position:"relative", isolation:"isolate" }}>
      <style>{`
        ${FONTS}
        * { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(0.85)} }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes sweep { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes slideIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes glow { 0%,100%{box-shadow:0 0 8px rgba(0,229,204,0.2)} 50%{box-shadow:0 0 18px rgba(0,229,204,0.45)} }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(0,229,204,0.2); border-radius:2px; }
      `}</style>
      <ScanLine />
      <button onClick={() => window.location.href='/'} style={{position:'fixed', top:16, right:32, zIndex:1000, background:'transparent', border:'none', color:'#00e5cc', cursor:'pointer', fontSize:24, fontFamily:'monospace'}}></button>

      {/* Noise overlay */}
      <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:1,
        backgroundImage:`url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E")`,
        backgroundSize:"200px", opacity:0.4 }} />

      <div style={{ position:"relative", zIndex:2 }}>

        {/* ── HEADER ── */}
        <header style={{ borderBottom:`1px solid ${C.borderB}`, padding:"0 32px",
          background:"rgba(8,12,24,0.95)", backdropFilter:"blur(12px)",
          position:"sticky", top:0, zIndex:100, display:"flex", alignItems:"stretch" }}>

          {/* Left: Brand */}
          <div style={{ display:"flex", alignItems:"center", gap:16, paddingRight:32,
            borderRight:`1px solid ${C.border}` }}>
            <div style={{ width:36, height:36, position:"relative" }}>
              <div style={{ width:"100%", height:"100%", border:`2px solid ${C.accent}`,
                transform:"rotate(45deg)", display:"flex", alignItems:"center", justifyContent:"center",
                animation:"glow 3s ease-in-out infinite" }}>
                <div style={{ width:8, height:8, background:C.accent, transform:"rotate(-45deg)" }} />
              </div>
            </div>
            <div>
              <div style={{ fontFamily:C.head, fontSize:22, letterSpacing:4, color:C.accent, lineHeight:1 }}>
                <Glitch text="SNIPERSIGHT" />
              </div>
              <div style={{ fontFamily:C.mono, fontSize:8, letterSpacing:3, color:C.muted }}>
                MARKET INTELLIGENCE COMMAND
              </div>
            </div>
          </div>

          {/* Center: Regime + Prices */}
          <div style={{ flex:1, display:"flex", alignItems:"center", gap:0, overflowX:"auto" }}>
            {[
              { sym:"BTC", price:fmt(data.btc.price), chg:data.btc.change },
              { sym:"ETH", price:fmt(data.eth.price), chg:data.eth.change },
              { sym:"SOL", price:fmt(data.sol.price), chg:data.sol.change },
              { sym:"BNB", price:fmt(data.bnb.price), chg:data.bnb.change },
            ].map((t,i) => (
              <div key={i} style={{ padding:"0 24px", borderRight:`1px solid ${C.border}`,
                display:"flex", flexDirection:"column", gap:2, justifyContent:"center", height:"100%",
                minWidth:110 }}>
                <div style={{ fontFamily:C.mono, fontSize:9, letterSpacing:2, color:C.muted }}>{t.sym}</div>
                <div style={{ fontFamily:C.mono, fontSize:13, color:C.text }}>{t.price}</div>
                <div style={{ fontFamily:C.mono, fontSize:10,
                  color:t.chg >= 0 ? C.green : C.red }}>{t.chg >= 0 ? "+" : ""}{t.chg}%</div>
              </div>
            ))}

            <div style={{ padding:"0 24px", display:"flex", flexDirection:"column", gap:4, justifyContent:"center", height:"100%" }}>
              <RegimeBadge regime={data.regime} />
            </div>
          </div>

          {/* Right: Time */}
          <div style={{ display:"flex", alignItems:"center", gap:16, paddingLeft:24,
            borderLeft:`1px solid ${C.border}` }}>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontFamily:C.mono, fontSize:10, color:C.muted, letterSpacing:1 }}>UTC</div>
              <div style={{ fontFamily:C.mono, fontSize:16, color:C.accent, letterSpacing:2 }}>
                {time.toUTCString().slice(17,25)}
              </div>
              <div style={{ fontFamily:C.mono, fontSize:9, color:C.muted, letterSpacing:1 }}>
                {time.toDateString()}
              </div>
            </div>
            <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
              <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted, letterSpacing:1 }}>STATUS</div>
              <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                <PulsingDot color={C.green} />
                <span style={{ fontFamily:C.mono, fontSize:9, color:C.green, letterSpacing:1 }}>LIVE</span>
              </div>
            </div>
          </div>
        </header>

        {/* ── TABS ── */}
        <div style={{ borderBottom:`1px solid ${C.border}`, padding:"0 32px",
          display:"flex", gap:0 }}>
          {tabs.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab.toLowerCase())}
              style={{ padding:"12px 24px", background:"none", border:"none",
                borderBottom: activeTab === tab.toLowerCase() ? `2px solid ${C.accent}` : "2px solid transparent",
                color: activeTab === tab.toLowerCase() ? C.accent : C.muted,
                fontFamily:C.mono, fontSize:10, letterSpacing:3, cursor:"pointer",
                textTransform:"uppercase", transition:"all 0.2s",
                marginBottom:-1 }}>
              {tab}
            </button>
          ))}
        </div>

        {/* ── MAIN CONTENT ── */}
        <main style={{ padding:"28px 32px", display:"flex", flexDirection:"column", gap:24 }}>

          {/* ─── ROW 1: Dominance + Fear/Greed + Regime + Cycle ─── */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 2fr", gap:16 }}>

            {/* Dominance Cards */}
            {[
              { label:"BTC DOMINANCE", value:fmtDom(data.btcDom), color:C.orange, note:"Risk-off signal", trend:"↑" },
              { label:"USDT DOMINANCE",value:fmtDom(data.usdtDom),color:C.red,    note:"Cash rotation ↑",trend:"↑" },
              { label:"ETH DOMINANCE", value:fmtDom(data.ethDom), color:C.accent, note:"Alt pressure",  trend:"↓" },
            ].map((d,i) => (
              <div key={i} style={card()}>
                <div style={{ position:"absolute", top:0, right:0, width:60, height:60, borderRadius:"0 4px 0 0",
                  background:`radial-gradient(circle at top right, ${d.color}14, transparent 70%)` }} />
                {label(d.label)}
                <div style={{ fontFamily:C.head, fontSize:44, color:d.color, lineHeight:1, letterSpacing:1 }}>
                  {d.value}
                  <span style={{ fontSize:22, marginLeft:6, color:d.color }}>{d.trend}</span>
                </div>
                <div style={{ fontFamily:C.mono, fontSize:9, color:C.muted, marginTop:6, letterSpacing:1 }}>{d.note}</div>
              </div>
            ))}

            {/* Fear & Greed + Cycle combined */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
              <div style={card({ display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center" })}>
                {label("FEAR & GREED INDEX", { marginBottom:12, textAlign:"center" })}
                <FearGreedGauge value={data.fearGreed} />
              </div>
              <div style={card()}>
                {label("4Y CYCLE POSITION")}
                <div style={{ fontFamily:C.head, fontSize:28, color:C.orange, letterSpacing:2, lineHeight:1 }}>
                  DISTRIBUTION
                </div>
                <div style={{ fontFamily:C.mono, fontSize:9, color:C.muted, marginTop:4, marginBottom:8 }}>
                  Smart money exiting • Manage risk
                </div>
                <CycleBar pct={data.cyclePct} day={data.cycleDay} />
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, marginTop:8 }}>
                  <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted, letterSpacing:1 }}>
                    <div style={{ color:C.text, fontSize:11 }}>Nov 2022</div>
                    LAST 4Y LOW
                  </div>
                  <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted, letterSpacing:1 }}>
                    <div style={{ color:C.orange, fontSize:11 }}>~Q4 2026</div>
                    EST. NEXT LOW
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ─── ROW 2: Liquidity Map + Signal Feed + Funding ─── */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1.4fr 1fr", gap:16 }}>

            {/* Liquidity Level Map */}
            <div style={card()}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16,
                borderBottom:`1px solid ${C.border}`, paddingBottom:12 }}>
                <div style={{ fontFamily:C.mono, fontSize:10, letterSpacing:2, color:C.accent }}>
                  LIQUIDITY MAP // BTC
                </div>
                <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted }}>KEY LEVELS</div>
              </div>
              <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
                {data.liquidityLevels.map((lvl,i) => {
                  const isCurrent = lvl.type === "current";
                  const isSell = lvl.type === "sell";
                  const isBuy = lvl.type === "buy";
                  return (
                    <div key={i} style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
                      padding:"7px 10px", borderRadius:3,
                      background: isCurrent ? "rgba(0,229,204,0.08)" : "rgba(255,255,255,0.02)",
                      border: isCurrent ? `1px solid ${C.accent}` : `1px solid transparent`,
                      borderLeft: `3px solid ${isCurrent ? C.accent : isSell ? C.red : C.green}`,
                      animation: isCurrent ? "glow 2s ease-in-out infinite" : "none" }}>
                      <span style={{ fontFamily:C.mono, fontSize:8, letterSpacing:1,
                        color: isCurrent ? C.accent : C.muted }}>{lvl.label}</span>
                      <span style={{ fontFamily:C.mono, fontSize:11,
                        color: isCurrent ? C.accent : isSell ? C.red : C.green,
                        fontWeight: isCurrent ? 700 : 400 }}>
                        ${lvl.price}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Live Signal Feed */}
            <div style={card()}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16,
                borderBottom:`1px solid ${C.border}`, paddingBottom:12 }}>
                <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                  <PulsingDot color={C.accent} />
                  <span style={{ fontFamily:C.mono, fontSize:10, letterSpacing:2, color:C.accent }}>LIVE SIGNAL FEED</span>
                </div>
                <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted }}>LAST 5 TRIGGERS</div>
              </div>
              <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                {data.signals.map((sig,i) => (
                  <div key={i} style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 14px",
                    background:"rgba(255,255,255,0.025)", borderRadius:4,
                    borderLeft:`3px solid ${signalColor(sig.dir)}`,
                    animation:`slideIn 0.3s ease ${i*0.05}s both` }}>
                    <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted, minWidth:32 }}>{sig.time}</div>
                    <div style={{ flex:1 }}>
                      <div style={{ fontFamily:C.mono, fontSize:11, color:C.text }}>{sig.asset}</div>
                      <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted, marginTop:2, letterSpacing:1 }}>
                        {sig.type} • {sig.tf}
                      </div>
                    </div>
                    <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                      {/* Score bar */}
                      <div style={{ display:"flex", flexDirection:"column", alignItems:"flex-end", gap:3 }}>
                        <div style={{ fontFamily:C.mono, fontSize:9, color:C.muted, letterSpacing:1 }}>SCORE</div>
                        <div style={{ width:60, height:4, background:"rgba(255,255,255,0.08)", borderRadius:2, overflow:"hidden" }}>
                          <div style={{ height:"100%", width:`${sig.score}%`, borderRadius:2,
                            background: sig.score > 80 ? C.green : sig.score > 60 ? C.yellow : C.orange,
                            boxShadow:`0 0 6px ${sig.score > 80 ? C.green : C.yellow}60` }} />
                        </div>
                        <div style={{ fontFamily:C.mono, fontSize:9, color: sig.score > 80 ? C.green : C.yellow }}>
                          {sig.score}
                        </div>
                      </div>
                      <div style={{ padding:"3px 8px", borderRadius:2, background:`${signalColor(sig.dir)}22`,
                        border:`1px solid ${signalColor(sig.dir)}44`,
                        fontFamily:C.mono, fontSize:9, color:signalColor(sig.dir), letterSpacing:1 }}>
                        {sig.dir}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop:14, padding:"10px 14px", background:"rgba(0,229,204,0.04)",
                borderRadius:4, border:`1px dashed ${C.borderB}`,
                fontFamily:C.mono, fontSize:9, color:C.muted, textAlign:"center", letterSpacing:2 }}>
                → OPEN SCANNER FOR FULL FEED
              </div>
            </div>

            {/* Funding Rates + OI */}
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              <div style={card()}>
                {label("FUNDING RATES")}
                {[
                  { sym:"BTC", rate:data.fundingBtc, oi:data.oiBtc },
                  { sym:"ETH", rate:data.fundingEth, oi:data.oiEth },
                ].map((f,i) => (
                  <div key={i} style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
                    padding:"10px 0", borderBottom: i === 0 ? `1px solid ${C.border}` : "none" }}>
                    <div>
                      <div style={{ fontFamily:C.mono, fontSize:12, color:C.text }}>{f.sym}/USDT</div>
                      <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted, marginTop:2 }}>OI: ${f.oi}</div>
                    </div>
                    <div style={{ textAlign:"right" }}>
                      <div style={{ fontFamily:C.mono, fontSize:14,
                        color: f.rate < -0.01 ? C.red : f.rate > 0.01 ? C.green : C.yellow }}>
                        {f.rate > 0 ? "+" : ""}{f.rate.toFixed(3)}%
                      </div>
                      <div style={{ fontFamily:C.mono, fontSize:8,
                        color: f.rate < 0 ? C.red : C.green, marginTop:2 }}>
                        {f.rate < -0.01 ? "SHORTS PAYING" : f.rate > 0.01 ? "LONGS PAYING" : "NEUTRAL"}
                      </div>
                    </div>
                  </div>
                ))}
                <div style={{ marginTop:10, padding:"8px 10px", borderRadius:3,
                  background:"rgba(255,68,102,0.07)", border:`1px solid rgba(255,68,102,0.2)`,
                  fontFamily:C.mono, fontSize:9, color:"rgba(255,68,102,0.8)", letterSpacing:1 }}>
                  ⚠ NEGATIVE FUNDING — SHORT SQUEEZE RISK
                </div>
              </div>

              {/* Market Brief Quickfire */}
              <div style={card({ flex:1 })}>
                {label("INTEL BRIEF")}
                <div style={{ fontFamily:C.head, fontSize:20, color:C.red, letterSpacing:2, marginBottom:10 }}>
                  BEARISH STRUCTURE
                </div>
                {[
                  { icon:"◉", text:"BOS on daily confirmed", color:C.red },
                  { icon:"◉", text:"BTC.D trending up — altcoin risk", color:C.orange },
                  { icon:"◉", text:"USDT.D rising — cash flight", color:C.orange },
                  { icon:"◎", text:"New daily cycle — watch for reversal", color:C.yellow },
                  { icon:"◎", text:"Reduce leverage. Wait for confirmation", color:C.muted },
                ].map((item,i) => (
                  <div key={i} style={{ display:"flex", gap:8, alignItems:"flex-start", marginBottom:7 }}>
                    <span style={{ fontFamily:C.mono, fontSize:10, color:item.color, marginTop:1 }}>{item.icon}</span>
                    <span style={{ fontFamily:C.body, fontSize:12, color:item.color, lineHeight:1.4 }}>{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ─── ROW 3: Narrative Tracker + Sparklines ─── */}
          <div style={{ display:"grid", gridTemplateColumns:"1.2fr 1fr", gap:16 }}>

            {/* Narrative Tracker */}
            <div style={card()}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16,
                borderBottom:`1px solid ${C.border}`, paddingBottom:12 }}>
                <span style={{ fontFamily:C.mono, fontSize:10, letterSpacing:2, color:C.accent }}>
                  NARRATIVE MOMENTUM TRACKER
                </span>
                <span style={{ fontFamily:C.mono, fontSize:8, color:C.muted }}>7D HEAT</span>
              </div>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:10 }}>
                {data.narratives.map((n,i) => {
                  const c = n.sector === "hot" ? C.green : n.sector === "warm" ? C.orange : C.muted;
                  return (
                    <div key={i} style={{ padding:"12px", borderRadius:4,
                      background: n.sector === "hot" ? "rgba(0,255,136,0.05)" : "rgba(255,255,255,0.02)",
                      border:`1px solid ${n.sector === "hot" ? "rgba(0,255,136,0.2)" : C.border}`,
                      display:"flex", flexDirection:"column", gap:6 }}>
                      <div style={{ fontFamily:C.mono, fontSize:9, color:C.text, letterSpacing:1 }}>{n.name}</div>
                      <div style={{ height:3, background:"rgba(255,255,255,0.06)", borderRadius:2, overflow:"hidden" }}>
                        <div style={{ height:"100%", width:`${n.strength}%`, background:c,
                          boxShadow:`0 0 6px ${c}60`, borderRadius:2, transition:"width 1s ease" }} />
                      </div>
                      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                        <span style={{ fontFamily:C.mono, fontSize:11, color:c }}>{n.strength}</span>
                        <span style={{ fontFamily:C.mono, fontSize:12, color:c }}>{n.trend}</span>
                      </div>
                      <div style={{ fontFamily:C.mono, fontSize:8, letterSpacing:2, color:c, textTransform:"uppercase",
                        opacity:0.8 }}>
                        {n.sector === "hot" ? "● HOT" : n.sector === "warm" ? "◎ WARM" : "○ COLD"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Watchlist with sparklines */}
            <div style={card()}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16,
                borderBottom:`1px solid ${C.border}`, paddingBottom:12 }}>
                <span style={{ fontFamily:C.mono, fontSize:10, letterSpacing:2, color:C.accent }}>WATCHLIST</span>
                <span style={{ fontFamily:C.mono, fontSize:8, color:C.muted }}>STRUCTURE STATUS</span>
              </div>
              {[
                { sym:"BTC/USDT", price:fmt(data.btc.price), chg:data.btc.change, status:"BEARISH BOS",    vol:data.btc.volume, pos:false },
                { sym:"ETH/USDT", price:fmt(data.eth.price), chg:data.eth.change, status:"BELOW 4H OB",   vol:data.eth.volume, pos:false },
                { sym:"SOL/USDT", price:fmt(data.sol.price), chg:data.sol.change, status:"DEMAND HOLD",   vol:data.sol.volume, pos:true  },
                { sym:"BNB/USDT", price:fmt(data.bnb.price), chg:data.bnb.change, status:"RANGING",       vol:data.bnb.volume, pos:false },
              ].map((w,i) => (
                <div key={i} style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 0",
                  borderBottom: i < 3 ? `1px solid ${C.border}` : "none" }}>
                  <div style={{ flex:1 }}>
                    <div style={{ fontFamily:C.mono, fontSize:11, color:C.text }}>{w.sym}</div>
                    <div style={{ fontFamily:C.mono, fontSize:8, color:C.muted, marginTop:2 }}>Vol ${w.vol}</div>
                  </div>
                  <MiniSparkline positive={w.pos} />
                  <div style={{ textAlign:"right", minWidth:80 }}>
                    <div style={{ fontFamily:C.mono, fontSize:12, color:C.text }}>{w.price}</div>
                    <div style={{ fontFamily:C.mono, fontSize:9,
                      color:w.chg >= 0 ? C.green : C.red }}>{w.chg >= 0 ? "+" : ""}{w.chg}%</div>
                    <div style={{ fontFamily:C.mono, fontSize:8, letterSpacing:1, marginTop:3,
                      color:w.pos ? C.green : C.red }}>{w.status}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ─── ROW 4: Bottom bar — Quick actions ─── */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4, 1fr)", gap:12 }}>
            {[
              { label:"LAUNCH SCANNER", sub:"Active Signals: 23", icon:"⌖", color:C.accent },
              { label:"OPEN AI BOT",    sub:"Ask SniperSight AI", icon:"◈", color:C.green  },
              { label:"RISK CALC",      sub:"Position Sizer",     icon:"◎", color:C.yellow },
              { label:"TRADE JOURNAL",  sub:"Log your trades",    icon:"◉", color:C.orange },
            ].map((btn,i) => (
              <button key={i} style={{ background:"transparent", border:`1px solid ${C.borderB}`,
                borderRadius:4, padding:"16px 20px", cursor:"pointer", textAlign:"left",
                display:"flex", alignItems:"center", gap:14,
                transition:"all 0.2s", position:"relative", overflow:"hidden",
                fontFamily:"inherit" }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = `${btn.color}0f`;
                  e.currentTarget.style.borderColor = `${btn.color}80`;
                  e.currentTarget.style.boxShadow = `0 0 20px ${btn.color}20`;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.borderColor = C.borderB;
                  e.currentTarget.style.boxShadow = "none";
                }}>
                <span style={{ fontFamily:C.mono, fontSize:22, color:btn.color }}>{btn.icon}</span>
                <div>
                  <div style={{ fontFamily:C.mono, fontSize:10, letterSpacing:2, color:btn.color }}>{btn.label}</div>
                  <div style={{ fontFamily:C.body, fontSize:11, color:C.muted, marginTop:2 }}>{btn.sub}</div>
                </div>
              </button>
            ))}
          </div>

        </main>
      </div>
    </div>
  );
}

export default Intel;

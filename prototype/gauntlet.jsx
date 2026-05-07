// ── Gauntlet Breakdown ──────────────────────────────────────
// Signal-funnel visualizer for Bot Status. Shows where each candidate
// signal died across the 21-stage filter chain.

const GAUNTLET_STAGES = [
  // group, id, label, hint
  { group:'PRE-SCORE',   id:'NO_DATA',           label:'NO DATA',            hint:'OHLCV missing for required TFs' },
  { group:'PRE-SCORE',   id:'MISSING_TF',        label:'MISSING TF',         hint:'Critical timeframe failed to load' },
  { group:'PRE-SCORE',   id:'STRUCTURAL_ANCHOR', label:'STRUCTURAL ANCHOR',  hint:'No valid HTF anchor (BOS/CHoCH/OB)' },
  { group:'PRE-SCORE',   id:'REGIME_ALIGNMENT',  label:'REGIME ALIGNMENT',   hint:'Direction conflicts with macro regime' },
  { group:'PRE-SCORE',   id:'BTC_IMPULSE',       label:'BTC IMPULSE',        hint:'BTC moving against the trade' },
  { group:'PRE-SCORE',   id:'CONFLICT_DENSITY',  label:'CONFLICT DENSITY',   hint:'Too many opposing signals nearby' },
  { group:'PRE-SCORE',   id:'COOLDOWN',          label:'COOLDOWN',           hint:'Symbol just lost / recently rejected' },
  { group:'POST-SCORE',  id:'CONFLUENCE',        label:'CONFLUENCE',         hint:'Score < mode min_confluence_score' },
  { group:'POST-SCORE',  id:'NO_TRADE_PLAN',     label:'NO TRADE PLAN',      hint:'Planner couldn\u2019t build entry/stop/TP' },
  { group:'POST-SCORE',  id:'RISK_VALIDATION',   label:'RISK VALIDATION',    hint:'R:R below min, or stops too wide/tight' },
  { group:'POST-SCORE',  id:'ML_GATE',           label:'ML GATE',            hint:'Edge model said skip' },
  { group:'EXECUTION',   id:'REGIME_VETO',       label:'REGIME VETO',        hint:'Late-stage regime check killed it' },
  { group:'EXECUTION',   id:'MAX_POSITIONS',     label:'MAX POSITIONS',      hint:'Already at concurrent-position cap' },
  { group:'EXECUTION',   id:'HAS_POSITION',      label:'HAS POSITION',       hint:'Already have a position on this symbol' },
  { group:'EXECUTION',   id:'PENDING_ORDER',     label:'PENDING ORDER',      hint:'Already have a pending order on this symbol' },
  { group:'EXECUTION',   id:'POSITION_SIZE',     label:'POSITION SIZE',      hint:'Sizing math returned zero / dust' },
  { group:'EXECUTION',   id:'PULLBACK_PROB',     label:'PULLBACK PROB',      hint:'Entry zone too far from price' },
  { group:'EXECUTION',   id:'PRICE_FETCH',       label:'PRICE FETCH',        hint:'Couldn\u2019t fetch current price' },
  { group:'EXECUTION',   id:'EXEC_ERROR',        label:'EXEC ERROR',         hint:'Exchange call failed' },
  { group:'EXECUTION',   id:'PENDING_FILL',      label:'PENDING FILL',       hint:'Order placed, waiting on fill' },
  { group:'EXECUTION',   id:'EXECUTED',          label:'EXECUTED',           hint:'Survived everything · position opened', terminal:true },
];

// Mock signal log — distributes ~52 candidates across stages so the funnel
// reads like a real session. In prod this comes from /api/bot/status.signal_log
const MOCK_SIGNALS = [
  // PRE-SCORE
  { sym:'JTO/USDT',  tf:'15m', dir:'LONG',  score:null, threshold:7.0, stage:'NO_DATA',           ts:'14:02:11', extra:'1H OHLCV pull failed' },
  { sym:'WLD/USDT',  tf:'15m', dir:'SHORT', score:null, threshold:7.0, stage:'MISSING_TF',        ts:'14:03:48', extra:'4H feed disconnected' },
  { sym:'PEPE/USDT', tf:'5m',  dir:'LONG',  score:null, threshold:7.0, stage:'STRUCTURAL_ANCHOR', ts:'14:05:02', extra:'no HTF BOS within 50 bars' },
  { sym:'INJ/USDT',  tf:'15m', dir:'SHORT', score:null, threshold:7.0, stage:'REGIME_ALIGNMENT',  ts:'14:06:33', extra:'macro: BULL · trade: SHORT' },
  { sym:'SUI/USDT',  tf:'15m', dir:'SHORT', score:null, threshold:7.0, stage:'REGIME_ALIGNMENT',  ts:'14:07:01', extra:'macro: BULL · trade: SHORT' },
  { sym:'ARB/USDT',  tf:'15m', dir:'LONG',  score:null, threshold:7.0, stage:'BTC_IMPULSE',       ts:'14:08:24', extra:'BTC −0.8% / 5m' },
  { sym:'OP/USDT',   tf:'15m', dir:'LONG',  score:null, threshold:7.0, stage:'BTC_IMPULSE',       ts:'14:08:51', extra:'BTC −0.8% / 5m' },
  { sym:'TIA/USDT',  tf:'15m', dir:'LONG',  score:null, threshold:7.0, stage:'CONFLICT_DENSITY',  ts:'14:09:18', extra:'4 opposing signals in 30m' },
  { sym:'AVAX/USDT', tf:'15m', dir:'SHORT', score:null, threshold:7.0, stage:'COOLDOWN',          ts:'14:10:55', extra:'lost 12m ago' },
  { sym:'LINK/USDT', tf:'15m', dir:'LONG',  score:null, threshold:7.0, stage:'COOLDOWN',          ts:'14:11:22', extra:'rejected 8m ago' },

  // POST-SCORE — CONFLUENCE is the bottleneck (18 signals)
  { sym:'NEAR/USDT', tf:'15m', dir:'LONG',  score:5.8, threshold:7.0, stage:'CONFLUENCE',         ts:'14:12:04' },
  { sym:'APT/USDT',  tf:'15m', dir:'LONG',  score:6.2, threshold:7.0, stage:'CONFLUENCE',         ts:'14:12:33' },
  { sym:'DYDX/USDT', tf:'15m', dir:'SHORT', score:6.4, threshold:7.0, stage:'CONFLUENCE',         ts:'14:13:01' },
  { sym:'MKR/USDT',  tf:'1H',  dir:'LONG',  score:5.5, threshold:7.0, stage:'CONFLUENCE',         ts:'14:13:18' },
  { sym:'GMT/USDT',  tf:'15m', dir:'LONG',  score:6.7, threshold:7.0, stage:'CONFLUENCE',         ts:'14:13:42' },
  { sym:'CRV/USDT',  tf:'15m', dir:'SHORT', score:6.1, threshold:7.0, stage:'CONFLUENCE',         ts:'14:14:11' },
  { sym:'AAVE/USDT', tf:'15m', dir:'LONG',  score:6.8, threshold:7.0, stage:'CONFLUENCE',         ts:'14:14:33' },
  { sym:'LDO/USDT',  tf:'15m', dir:'LONG',  score:5.9, threshold:7.0, stage:'CONFLUENCE',         ts:'14:15:01' },
  { sym:'GMX/USDT',  tf:'15m', dir:'SHORT', score:6.3, threshold:7.0, stage:'CONFLUENCE',         ts:'14:15:24' },
  { sym:'STRK/USDT', tf:'15m', dir:'LONG',  score:6.6, threshold:7.0, stage:'CONFLUENCE',         ts:'14:15:48' },
  { sym:'PYTH/USDT', tf:'15m', dir:'LONG',  score:5.7, threshold:7.0, stage:'CONFLUENCE',         ts:'14:16:12' },
  { sym:'JUP/USDT',  tf:'15m', dir:'SHORT', score:6.5, threshold:7.0, stage:'CONFLUENCE',         ts:'14:16:38' },
  { sym:'MANTA/USDT',tf:'15m', dir:'LONG',  score:6.0, threshold:7.0, stage:'CONFLUENCE',         ts:'14:17:01' },
  { sym:'ENA/USDT',  tf:'15m', dir:'LONG',  score:6.4, threshold:7.0, stage:'CONFLUENCE',         ts:'14:17:24' },
  { sym:'IMX/USDT',  tf:'15m', dir:'SHORT', score:6.2, threshold:7.0, stage:'CONFLUENCE',         ts:'14:17:48' },
  { sym:'ONDO/USDT', tf:'15m', dir:'LONG',  score:6.9, threshold:7.0, stage:'CONFLUENCE',         ts:'14:18:11' },
  { sym:'WIF/USDT',  tf:'5m',  dir:'LONG',  score:6.1, threshold:7.0, stage:'CONFLUENCE',         ts:'14:18:33' },
  { sym:'BONK/USDT', tf:'5m',  dir:'LONG',  score:5.4, threshold:7.0, stage:'CONFLUENCE',         ts:'14:18:51' },
  { sym:'FET/USDT',  tf:'15m', dir:'SHORT', score:7.1, threshold:7.0, stage:'NO_TRADE_PLAN',      ts:'14:19:18', extra:'no valid OB within 1.5R' },
  { sym:'RNDR/USDT', tf:'15m', dir:'LONG',  score:7.3, threshold:7.0, stage:'NO_TRADE_PLAN',      ts:'14:19:42', extra:'TP1 inside spread' },
  { sym:'FIL/USDT',  tf:'15m', dir:'LONG',  score:7.2, threshold:7.0, stage:'RISK_VALIDATION',    ts:'14:20:11', extra:'R:R 0.92 < 1.50 min' },
  { sym:'ATOM/USDT', tf:'15m', dir:'SHORT', score:7.4, threshold:7.0, stage:'RISK_VALIDATION',    ts:'14:20:38', extra:'stop too tight (0.18%)' },
  { sym:'DOT/USDT',  tf:'15m', dir:'LONG',  score:7.6, threshold:7.0, stage:'RISK_VALIDATION',    ts:'14:21:04', extra:'R:R 1.14 < 1.50 min' },
  { sym:'XRP/USDT',  tf:'15m', dir:'LONG',  score:7.5, threshold:7.0, stage:'ML_GATE',            ts:'14:21:28', extra:'edge p=0.41 < 0.55' },
  { sym:'ADA/USDT',  tf:'15m', dir:'SHORT', score:7.3, threshold:7.0, stage:'ML_GATE',            ts:'14:21:52', extra:'edge p=0.46 < 0.55' },

  // EXECUTION
  { sym:'LTC/USDT',  tf:'15m', dir:'LONG',  score:7.8, threshold:7.0, stage:'REGIME_VETO',        ts:'14:22:18', extra:'4H regime flipped CHOP' },
  { sym:'BCH/USDT',  tf:'15m', dir:'SHORT', score:7.6, threshold:7.0, stage:'MAX_POSITIONS',      ts:'14:22:44', extra:'4/4 slots full' },
  { sym:'BTC/USDT',  tf:'15m', dir:'LONG',  score:8.2, threshold:7.0, stage:'HAS_POSITION',       ts:'14:23:01', extra:'already long BTC' },
  { sym:'ETH/USDT',  tf:'15m', dir:'LONG',  score:7.9, threshold:7.0, stage:'PENDING_ORDER',      ts:'14:23:25', extra:'limit order live @ 3198' },
  { sym:'STX/USDT',  tf:'15m', dir:'LONG',  score:7.5, threshold:7.0, stage:'POSITION_SIZE',      ts:'14:23:48', extra:'$8 size after risk math' },
  { sym:'KAS/USDT',  tf:'15m', dir:'LONG',  score:7.7, threshold:7.0, stage:'PULLBACK_PROB',      ts:'14:24:11', extra:'entry 0.8% from price' },
  { sym:'TON/USDT',  tf:'15m', dir:'LONG',  score:7.8, threshold:7.0, stage:'PRICE_FETCH',        ts:'14:24:38', extra:'mark-price RPC timeout' },
  { sym:'ENS/USDT',  tf:'15m', dir:'SHORT', score:7.6, threshold:7.0, stage:'EXEC_ERROR',         ts:'14:25:01', extra:'Bybit · -1013 size precision' },
  { sym:'SEI/USDT',  tf:'15m', dir:'LONG',  score:7.9, threshold:7.0, stage:'PENDING_FILL',       ts:'14:25:24', extra:'limit @ 0.412 · 18s old' },

  // EXECUTED
  { sym:'BTC/USDT',  tf:'15m', dir:'LONG',  score:8.4, threshold:7.0, stage:'EXECUTED',           ts:'13:54:18', extra:'+0.42% · TP1 hit' },
  { sym:'SOL/USDT',  tf:'15m', dir:'LONG',  score:8.1, threshold:7.0, stage:'EXECUTED',           ts:'14:01:42', extra:'+0.18% · running' },
];

// Auto-detect the dominant kill stage and produce an actionable insight
function deriveBottleneck(counts){
  // Skip terminal & ok-for-now stages
  const skip = new Set(['EXECUTED','PENDING_FILL']);
  const total = Object.entries(counts).reduce((s,[k,v])=> skip.has(k) ? s : s+v, 0);
  if (total === 0) return null;
  let topId = null, topCount = 0;
  for (const [id,c] of Object.entries(counts)){
    if (skip.has(id)) continue;
    if (c > topCount) { topCount = c; topId = id; }
  }
  if (!topId || topCount === 0) return null;
  const pct = Math.round((topCount/total)*100);

  const ACTION_MAP = {
    CONFLUENCE:        { msg:'Confluence threshold may be too high for current conditions.', cta:'Switch to STRIKE (≥6.8)', href:'Bot.html#setup' },
    REGIME_ALIGNMENT:  { msg:'Most signals fight the macro regime — your direction bias is wrong.', cta:'Review regime detector', href:'Intel.html' },
    REGIME_VETO:       { msg:'Late-stage regime check is killing approved plans.', cta:'Inspect regime detector', href:'Intel.html' },
    BTC_IMPULSE:       { msg:'BTC volatility is breaking signals before entry.', cta:'Open BTC chart', href:'Intel.html#btc' },
    RISK_VALIDATION:   { msg:'Plans don\u2019t meet R:R floor — stops or TPs need recalibrating.', cta:'Tune risk params', href:'Settings.html' },
    ML_GATE:           { msg:'Edge model is rejecting most signals — model may be stale.', cta:'Retrain model', href:'Training.html' },
    MAX_POSITIONS:     { msg:'Concurrent-position cap is the bottleneck, not detection.', cta:'Raise cap in Risk Center', href:'Settings.html' },
    COOLDOWN:          { msg:'Cooldown filter eating most signals — recent loss streak.', cta:'Review Journal', href:'Journal.html' },
    NO_TRADE_PLAN:     { msg:'Planner can\u2019t build valid plans — anchors may be too sparse.', cta:'Tune planner', href:'Bot.html#triggers' },
    STRUCTURAL_ANCHOR: { msg:'No HTF anchors are forming — market is choppy.', cta:'Wait for trend', href:'Intel.html' },
    EXEC_ERROR:        { msg:'Exchange is rejecting orders — check API keys / size precision.', cta:'Open Risk Center', href:'Settings.html' },
  };
  const action = ACTION_MAP[topId] || { msg:'Investigate this stage in detail mode.', cta:'View detail', href:'#' };
  const stage = GAUNTLET_STAGES.find(s=>s.id===topId);
  return { id:topId, label: stage?.label || topId, count: topCount, pct, ...action };
}

function GauntletBreakdown({ signals }){
  const sigs = signals || MOCK_SIGNALS;
  const [detail, setDetail] = useState(false);
  const [filterStage, setFilterStage] = useState(null);

  const counts = useMemo(()=>{
    const c = {};
    GAUNTLET_STAGES.forEach(s=>{ c[s.id] = 0; });
    sigs.forEach(s => { c[s.stage] = (c[s.stage]||0) + 1; });
    return c;
  }, [sigs]);

  const total = sigs.length;
  const executed = counts['EXECUTED'] || 0;
  const conversion = total > 0 ? (executed/total)*100 : 0;
  const bottleneck = useMemo(()=>deriveBottleneck(counts), [counts]);

  // Max count for bar scaling (excluding zero stages for nicer look)
  const maxCount = Math.max(...Object.values(counts), 1);

  // Group stages
  const groups = ['PRE-SCORE','POST-SCORE','EXECUTION'];

  const stageColor = (id, count) => {
    if (count === 0) return 'var(--fg-4)';
    if (id === 'EXECUTED') return 'var(--green-soft)';
    if (id === 'PENDING_FILL') return 'var(--amber-2)';
    return 'var(--red-2)';
  };
  const stageBg = (id, count) => {
    if (count === 0) return 'transparent';
    if (id === 'EXECUTED') return 'rgba(74,222,128,.12)';
    if (id === 'PENDING_FILL') return 'rgba(251,191,36,.10)';
    return 'rgba(248,113,113,.10)';
  };

  const filteredSigs = filterStage ? sigs.filter(s=>s.stage===filterStage) : sigs;

  return (
    <section className="panel">
      <div className="sec-head">
        <div className="sec-title"><span className="dot"/> Gauntlet Breakdown</div>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span className="chip">{total} CANDIDATES · {executed} EXECUTED · {conversion.toFixed(1)}%</span>
          <button className="btn" onClick={()=>setDetail(!detail)} style={{padding:'4px 10px',fontSize:9,letterSpacing:'.18em'}}>{detail?'◉ DETAIL':'◯ DETAIL'}</button>
        </div>
      </div>

      {/* Bottleneck insight pill */}
      {bottleneck && (
        <div style={{margin:'14px 18px 0',padding:'10px 14px',border:'1px solid var(--amber-border)',borderRadius:8,background:'var(--amber-bg)',display:'flex',alignItems:'center',gap:14,flexWrap:'wrap'}}>
          <div style={{display:'flex',alignItems:'center',gap:8}}>
            <span style={{color:'var(--amber-2)',fontSize:14}}>⚠</span>
            <span className="mono" style={{fontSize:9,color:'var(--amber-2)',letterSpacing:'.18em',fontWeight:700}}>BOTTLENECK</span>
            <span className="mono" style={{fontSize:11,color:'var(--fg)',fontWeight:700,letterSpacing:'.14em'}}>{bottleneck.label}</span>
            <span className="mono" style={{fontSize:10,color:'var(--fg-3)'}}>· {bottleneck.count} signals · {bottleneck.pct}% of rejects</span>
          </div>
          <div style={{flex:1,minWidth:200,fontSize:11,color:'var(--fg-2)',lineHeight:1.4}}>{bottleneck.msg}</div>
          <a href={bottleneck.href} className="btn" style={{padding:'5px 12px',fontSize:10,letterSpacing:'.16em',textDecoration:'none',background:'var(--amber-bg)',borderColor:'var(--amber-border)',color:'var(--amber-2)'}}>{bottleneck.cta} →</a>
        </div>
      )}

      {/* Funnel */}
      <div style={{padding:'14px 18px',display:'grid',gridTemplateColumns:detail?'1fr':'1fr 1fr 1fr',gap:18}}>
        {groups.map(g=>(
          <div key={g}>
            <div className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.20em',marginBottom:8,paddingBottom:6,borderBottom:'1px dashed var(--border-soft)'}}>// {g} {g==='PRE-SCORE'?'· cheap rejects':g==='POST-SCORE'?'· after confluence math':'· execution layer'}</div>
            <div style={{display:'flex',flexDirection:'column',gap:detail?2:3}}>
              {GAUNTLET_STAGES.filter(s=>s.group===g).map(s=>{
                const c = counts[s.id] || 0;
                const w = (c/maxCount)*100;
                const sel = filterStage === s.id;
                return (
                  <div key={s.id}
                       onClick={()=>setFilterStage(sel?null:s.id)}
                       title={s.hint}
                       style={{display:'grid',gridTemplateColumns:detail?'160px 1fr 50px':'130px 1fr 32px',gap:8,alignItems:'center',padding:'5px 8px',borderRadius:4,cursor:'pointer',background:sel?'rgba(255,255,255,.04)':'transparent',border:sel?'1px solid var(--accent-border)':'1px solid transparent',transition:'all .15s'}}>
                    <span className="mono" style={{fontSize:9,color: c===0?'var(--fg-4)':'var(--fg-2)',letterSpacing:'.10em',fontWeight:c>0?700:400,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.label}</span>
                    <div style={{height:detail?16:12,background:'rgba(0,0,0,.35)',borderRadius:2,position:'relative',overflow:'hidden',border:'1px solid var(--border-soft)'}}>
                      <div style={{position:'absolute',left:0,top:0,bottom:0,width:`${w}%`,background:stageBg(s.id,c),borderRight:c>0?`2px solid ${stageColor(s.id,c)}`:'none',transition:'width .3s'}}/>
                    </div>
                    <span className="mono" style={{fontSize:10,fontWeight:700,color:stageColor(s.id,c),textAlign:'right',letterSpacing:'.06em'}}>{c}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Detail rows — visible when DETAIL toggle on, OR when filtering by stage */}
      {(detail || filterStage) && (
        <div style={{padding:'0 18px 18px'}}>
          <div style={{paddingTop:10,borderTop:'1px dashed var(--border-soft)'}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10}}>
              <span className="mono" style={{fontSize:9,color:'var(--fg-4)',letterSpacing:'.20em'}}>// {filterStage ? `STAGE: ${filterStage}` : 'ALL SIGNALS'} · {filteredSigs.length} ROWS</span>
              {filterStage && <button className="btn" onClick={()=>setFilterStage(null)} style={{padding:'3px 10px',fontSize:9,letterSpacing:'.16em'}}>× CLEAR FILTER</button>}
            </div>
            <table className="mono" style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
              <thead>
                <tr style={{textAlign:'left',color:'var(--fg-4)',fontSize:9,letterSpacing:'.18em',textTransform:'uppercase'}}>
                  <th style={{padding:'4px 0'}}>Time</th>
                  <th>Symbol</th>
                  <th>TF</th>
                  <th>Side</th>
                  <th>Score</th>
                  <th>Stage</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {filteredSigs.slice().reverse().map((s,i)=>{
                  const c = stageColor(s.stage, 1);
                  return (
                    <tr key={i} style={{borderTop:'1px dashed var(--border-soft)'}}>
                      <td style={{padding:'6px 0',color:'var(--fg-4)',fontSize:10}}>{s.ts}</td>
                      <td style={{fontWeight:700}}>{s.sym}</td>
                      <td style={{color:'var(--fg-3)'}}>{s.tf}</td>
                      <td style={{color:s.dir==='LONG'?'var(--green-soft)':'var(--red-2)',fontWeight:700,fontSize:10,letterSpacing:'.12em'}}>{s.dir}</td>
                      <td style={{color: s.score==null ? 'var(--fg-4)' : s.score>=s.threshold?'var(--green-soft)':'var(--red-2)'}}>
                        {s.score==null ? '—' : `${s.score.toFixed(1)} / ${s.threshold.toFixed(1)}`}
                      </td>
                      <td><span style={{color:c,fontWeight:700,fontSize:9,letterSpacing:'.14em',padding:'2px 8px',border:`1px solid ${c}`,borderRadius:3,background:stageBg(s.stage,1)}}>{s.stage}</span></td>
                      <td style={{color:'var(--fg-3)',fontSize:10}}>{s.extra || '—'}</td>
                    </tr>
                  );
                })}
                {filteredSigs.length === 0 && (
                  <tr><td colSpan={7} style={{textAlign:'center',padding:'20px 0',color:'var(--fg-4)',fontSize:11,letterSpacing:'.16em'}}>// no signals at this stage</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

window.GauntletBreakdown = GauntletBreakdown;

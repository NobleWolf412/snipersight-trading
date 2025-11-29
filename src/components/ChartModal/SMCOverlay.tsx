import React from 'react';
import type { ScanResult } from '@/utils/mockData';

interface SMCOverlayProps {
  result: ScanResult;
  show: {
    orderBlocks: boolean;
    fvgs: boolean;
    bosChoch: boolean;
    sweeps: boolean;
  };
  timeframe?: string; // "15" | "60" | "240" | "D"
  density?: 'low' | 'medium' | 'high';
}

// Lightweight SVG overlay to visualize SMC geometry roughly aligned by price.
// NOTE: This is an approximate renderer since TradingView iframe doesn't expose chart coordinates.
// We scale levels within a min/max range extracted from known prices (entry zone, stop, TPs, geometry).
export function SMCOverlay({ result, show, timeframe = '60', density = 'medium' }: SMCOverlayProps) {
  const geo = result.smc_geometry || {};
  const levels: number[] = [];
  const ranges: Array<{ low: number; high: number; type: 'OB' | 'FVG' }> = [];

  // Density caps to reduce clutter
  const baseCaps = {
    low: { ob: 10, fvg: 10, brk: 20, sweep: 15 },
    medium: { ob: 20, fvg: 20, brk: 50, sweep: 30 },
    high: { ob: 40, fvg: 40, brk: 100, sweep: 50 },
  } as const;
  const tfMultiplier = (() => {
    switch (timeframe) {
      case 'D':
        return 0.4; // stronger downscale on daily
      case '240':
        return 0.7; // stronger downscale on 4H
      default:
        return 1.0; // 60 or 15
    }
  })();
  const caps = {
    ob: Math.max(1, Math.floor(baseCaps[density].ob * tfMultiplier)),
    fvg: Math.max(1, Math.floor(baseCaps[density].fvg * tfMultiplier)),
    brk: Math.max(5, Math.floor(baseCaps[density].brk * tfMultiplier)),
    sweep: Math.max(5, Math.floor(baseCaps[density].sweep * tfMultiplier)),
  };

  // Collect baseline levels
  levels.push(result.entryZone.low, result.entryZone.high, result.stopLoss, ...result.takeProfits);

  // Collect geometry-derived levels/ranges
  if (show.orderBlocks && Array.isArray(geo.order_blocks)) {
    geo.order_blocks.slice(0, caps.ob).forEach((ob: any) => {
      if (typeof ob.price === 'number') levels.push(ob.price);
      if (typeof ob.low === 'number' && typeof ob.high === 'number') ranges.push({ low: ob.low, high: ob.high, type: 'OB' });
    });
  }
  if (show.fvgs && Array.isArray(geo.fvgs)) {
    geo.fvgs.slice(0, caps.fvg).forEach((fvg: any) => {
      if (typeof fvg.low === 'number' && typeof fvg.high === 'number') ranges.push({ low: fvg.low, high: fvg.high, type: 'FVG' });
    });
  }
  if (show.bosChoch && Array.isArray(geo.bos_choch)) {
    geo.bos_choch.slice(0, caps.brk).forEach((brk: any) => {
      if (typeof brk.level === 'number') levels.push(brk.level);
    });
  }
  if (show.sweeps && Array.isArray(geo.liquidity_sweeps)) {
    geo.liquidity_sweeps.slice(0, caps.sweep).forEach((sw: any) => {
      if (typeof sw.level === 'number') levels.push(sw.level);
    });
  }

  // Determine min/max for scaling
  const min = Math.min(...levels);
  const max = Math.max(...levels);

  // Helper: map price to Y percentage (invert so higher price is higher on chart)
  const yPct = (price: number) => {
    if (!Number.isFinite(min) || !Number.isFinite(max) || max === min) return 50;
    const t = (price - min) / (max - min);
    return 100 - t * 100; // invert for top-down SVG
  };

  // Colors
  const colors = {
    ob: '#22c55e', // green
    fvg: '#60a5fa', // blue
    brk: '#f59e0b', // amber
    sweep: '#ef4444', // red
  };

  return (
    <div className="absolute inset-0 pointer-events-none">
      <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {/* Ranges (OB/FVG) */}
        {ranges.map((r, i) => {
          const y1 = yPct(r.high);
          const y2 = yPct(r.low);
          const h = Math.max(1, Math.abs(y2 - y1));
          const color = r.type === 'OB' ? colors.ob : colors.fvg;
          return (
            <g key={`range-${r.type}-${i}`} aria-label={r.type === 'OB' ? 'Order Block' : 'Fair Value Gap'}>
              <rect x={5} y={Math.min(y1, y2)} width={90} height={h}
                fill={color + '22'} stroke={color} strokeWidth={0.4} />
              <title>{r.type === 'OB' ? 'Order Block: last opposing candle zone' : 'FVG: liquidity imbalance gap'}</title>
            </g>
          );
        })}
        {/* Levels (BOS/CHoCH, sweeps, single OB levels) */}
        {show.bosChoch && Array.isArray(geo.bos_choch) && geo.bos_choch.slice(0, caps.brk).map((brk: any, i: number) => {
          if (typeof brk.level !== 'number') return null;
          const y = yPct(brk.level);
          return (
            <g key={`bos-${i}`} aria-label="BOS/CHoCH">
              <line x1={5} x2={95} y1={y} y2={y}
                stroke={colors.brk} strokeWidth={0.5} strokeDasharray="2,2" />
              <title>Structure break: trend continuation (BOS) or reversal (CHoCH)</title>
            </g>
          );
        })}
        {show.sweeps && Array.isArray(geo.liquidity_sweeps) && geo.liquidity_sweeps.slice(0, caps.sweep).map((sw: any, i: number) => {
          if (typeof sw.level !== 'number') return null;
          const y = yPct(sw.level);
          return (
            <g key={`sweep-${i}`} aria-label="Liquidity Sweep">
              <line x1={5} x2={95} y1={y} y2={y}
                stroke={colors.sweep} strokeWidth={0.6} strokeDasharray="1,2" />
              <title>Liquidity sweep: wick beyond recent high/low followed by rejection</title>
            </g>
          );
        })}
      </svg>
      {/* Legend */}
      <div className="absolute top-2 left-2 bg-black/40 backdrop-blur rounded px-2 py-1 text-[10px] text-foreground border border-border">
        <span className="mr-2" style={{ color: colors.ob }}>OB</span>
        <span className="mr-2" style={{ color: colors.fvg }}>FVG</span>
        <span className="mr-2" style={{ color: colors.brk }}>BOS/CHoCH</span>
        <span style={{ color: colors.sweep }}>Sweep</span>
      </div>
      {/* Tooltip hint */}
      <div className="absolute top-2 right-2 text-[10px] text-muted-foreground bg-black/30 rounded px-2 py-1 border border-border">
        Hover lines/boxes for explanations
      </div>
    </div>
  );
}

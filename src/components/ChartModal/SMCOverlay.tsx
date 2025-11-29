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
}

// Lightweight SVG overlay to visualize SMC geometry roughly aligned by price.
// NOTE: This is an approximate renderer since TradingView iframe doesn't expose chart coordinates.
// We scale levels within a min/max range extracted from known prices (entry zone, stop, TPs, geometry).
export function SMCOverlay({ result, show }: SMCOverlayProps) {
  const geo = result.smc_geometry || {};
  const levels: number[] = [];
  const ranges: Array<{ low: number; high: number; type: 'OB' | 'FVG' }> = [];

  // Collect baseline levels
  levels.push(result.entryZone.low, result.entryZone.high, result.stopLoss, ...result.takeProfits);

  // Collect geometry-derived levels/ranges
  if (show.orderBlocks && Array.isArray(geo.order_blocks)) {
    geo.order_blocks.forEach((ob: any) => {
      if (typeof ob.price === 'number') levels.push(ob.price);
      if (typeof ob.low === 'number' && typeof ob.high === 'number') ranges.push({ low: ob.low, high: ob.high, type: 'OB' });
    });
  }
  if (show.fvgs && Array.isArray(geo.fvgs)) {
    geo.fvgs.forEach((fvg: any) => {
      if (typeof fvg.low === 'number' && typeof fvg.high === 'number') ranges.push({ low: fvg.low, high: fvg.high, type: 'FVG' });
    });
  }
  if (show.bosChoch && Array.isArray(geo.bos_choch)) {
    geo.bos_choch.forEach((brk: any) => {
      if (typeof brk.level === 'number') levels.push(brk.level);
    });
  }
  if (show.sweeps && Array.isArray(geo.liquidity_sweeps)) {
    geo.liquidity_sweeps.forEach((sw: any) => {
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
            <g key={`range-${r.type}-${i}`}>
              <rect x={5} y={Math.min(y1, y2)} width={90} height={h}
                fill={color + '22'} stroke={color} strokeWidth={0.4} />
            </g>
          );
        })}
        {/* Levels (BOS/CHoCH, sweeps, single OB levels) */}
        {show.bosChoch && Array.isArray(geo.bos_choch) && geo.bos_choch.map((brk: any, i: number) => {
          if (typeof brk.level !== 'number') return null;
          const y = yPct(brk.level);
          return (
            <line key={`bos-${i}`} x1={5} x2={95} y1={y} y2={y}
              stroke={colors.brk} strokeWidth={0.5} strokeDasharray="2,2" />
          );
        })}
        {show.sweeps && Array.isArray(geo.liquidity_sweeps) && geo.liquidity_sweeps.map((sw: any, i: number) => {
          if (typeof sw.level !== 'number') return null;
          const y = yPct(sw.level);
          return (
            <line key={`sweep-${i}`} x1={5} x2={95} y1={y} y2={y}
              stroke={colors.sweep} strokeWidth={0.6} strokeDasharray="1,2" />
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
    </div>
  );
}

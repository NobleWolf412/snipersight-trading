import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { ScanResult } from '@/utils/mockData';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { 
  TrendUp, 
  TrendDown, 
  ArrowsOutLineHorizontal, 
  Target,
  ChartLine
} from '@phosphor-icons/react';

interface CandleData {
  time: Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface TradingViewChartProps {
  result: ScanResult;
}

export function TradingViewChart({ result }: TradingViewChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [timeframe, setTimeframe] = useState('1H');
  const [showLevels, setShowLevels] = useState({
    entry: true,
    stopLoss: true,
    takeProfits: true,
    orderBlocks: true,
    fvg: true
  });

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const candleData = generateCandleData(result, timeframe);
    drawChart(candleData);
  }, [result, timeframe, showLevels]);

  const generateCandleData = (result: ScanResult, tf: string): CandleData[] => {
    const numCandles = tf === '15m' ? 96 : tf === '1H' ? 48 : tf === '4H' ? 24 : 30;
    const data: CandleData[] = [];
    const now = new Date();
    const currentPrice = result.entryZone.high;
    
    let price = currentPrice * 0.95;
    const trend = result.trendBias === 'BULLISH' ? 1 : result.trendBias === 'BEARISH' ? -1 : 0;

    for (let i = numCandles; i >= 0; i--) {
      const time = new Date(now.getTime() - i * getTimeframeMs(tf));
      const volatility = currentPrice * 0.005;
      
      const open = price;
      const trendMove = trend * volatility * (Math.random() * 0.5 + 0.5);
      const close = open + trendMove + (Math.random() - 0.5) * volatility;
      
      const high = Math.max(open, close) + Math.random() * volatility;
      const low = Math.min(open, close) - Math.random() * volatility;
      const volume = Math.random() * 1000000 + 500000;
      
      data.push({ time, open, high, low, close, volume });
      price = close;
    }

    const lastClose = data[data.length - 1].close;
    const adjustment = currentPrice / lastClose;
    return data.map(d => ({
      ...d,
      open: d.open * adjustment,
      high: d.high * adjustment,
      low: d.low * adjustment,
      close: d.close * adjustment
    }));
  };

  const getTimeframeMs = (tf: string): number => {
    const map: Record<string, number> = {
      '15m': 15 * 60 * 1000,
      '1H': 60 * 60 * 1000,
      '4H': 4 * 60 * 60 * 1000,
      '1D': 24 * 60 * 60 * 1000
    };
    return map[tf] || map['1H'];
  };

  const drawChart = (data: CandleData[]) => {
    if (!svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const containerWidth = container.clientWidth;
    const containerHeight = 500;

    const margin = { top: 20, right: 80, bottom: 60, left: 60 };
    const width = containerWidth - margin.left - margin.right;
    const height = containerHeight - margin.top - margin.bottom;

    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', containerWidth)
      .attr('height', containerHeight);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3.scaleTime()
      .domain(d3.extent(data, d => d.time) as [Date, Date])
      .range([0, width]);

    const allPrices = data.flatMap(d => [d.high, d.low]);
    const yScale = d3.scaleLinear()
      .domain([d3.min(allPrices)! * 0.995, d3.max(allPrices)! * 1.005])
      .range([height, 0]);

    g.append('rect')
      .attr('width', width)
      .attr('height', height)
      .attr('fill', 'oklch(0.141 0.005 285.823)')
      .attr('rx', 4);

    const gridColor = 'oklch(0.37 0.013 285.805 / 0.1)';
    const yTicks = yScale.ticks(8);
    g.selectAll('.grid-line-y')
      .data(yTicks)
      .enter()
      .append('line')
      .attr('class', 'grid-line-y')
      .attr('x1', 0)
      .attr('x2', width)
      .attr('y1', d => yScale(d))
      .attr('y2', d => yScale(d))
      .attr('stroke', gridColor)
      .attr('stroke-width', 1);

    const candleWidth = Math.max(2, Math.min(12, width / data.length * 0.7));

    data.forEach((d) => {
      const x = xScale(d.time);
      const isGreen = d.close >= d.open;
      const color = isGreen ? 'oklch(0.75 0.18 140)' : 'oklch(0.704 0.191 22.216)';

      g.append('line')
        .attr('x1', x)
        .attr('x2', x)
        .attr('y1', yScale(d.high))
        .attr('y2', yScale(d.low))
        .attr('stroke', color)
        .attr('stroke-width', 1);

      g.append('rect')
        .attr('x', x - candleWidth / 2)
        .attr('y', yScale(Math.max(d.open, d.close)))
        .attr('width', candleWidth)
        .attr('height', Math.max(1, Math.abs(yScale(d.open) - yScale(d.close))))
        .attr('fill', color);
    });

    if (showLevels.entry) {
      const entryGroup = g.append('g').attr('class', 'entry-zone');
      
      entryGroup.append('rect')
        .attr('x', 0)
        .attr('y', yScale(result.entryZone.high))
        .attr('width', width)
        .attr('height', yScale(result.entryZone.low) - yScale(result.entryZone.high))
        .attr('fill', 'oklch(0.75 0.18 140 / 0.1)')
        .attr('stroke', 'oklch(0.75 0.18 140)')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '4,4');

      entryGroup.append('text')
        .attr('x', width - 5)
        .attr('y', yScale(result.entryZone.high) - 5)
        .attr('text-anchor', 'end')
        .attr('fill', 'oklch(0.75 0.18 140)')
        .attr('font-size', '11px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .text('ENTRY ZONE');
    }

    if (showLevels.stopLoss) {
      const slGroup = g.append('g').attr('class', 'stop-loss');
      
      slGroup.append('line')
        .attr('x1', 0)
        .attr('x2', width)
        .attr('y1', yScale(result.stopLoss))
        .attr('y2', yScale(result.stopLoss))
        .attr('stroke', 'oklch(0.704 0.191 22.216)')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '8,4');

      slGroup.append('text')
        .attr('x', width - 5)
        .attr('y', yScale(result.stopLoss) - 5)
        .attr('text-anchor', 'end')
        .attr('fill', 'oklch(0.704 0.191 22.216)')
        .attr('font-size', '11px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(`SL: $${result.stopLoss.toFixed(2)}`);
    }

    if (showLevels.takeProfits) {
      result.takeProfits.forEach((tp, i) => {
        const tpGroup = g.append('g').attr('class', `take-profit-${i}`);
        
        tpGroup.append('line')
          .attr('x1', 0)
          .attr('x2', width)
          .attr('y1', yScale(tp))
          .attr('y2', yScale(tp))
          .attr('stroke', 'oklch(0.527 0.154 150.069)')
          .attr('stroke-width', 1.5)
          .attr('stroke-dasharray', '6,3');

        tpGroup.append('text')
          .attr('x', width - 5)
          .attr('y', yScale(tp) + (i % 2 === 0 ? -5 : 15))
          .attr('text-anchor', 'end')
          .attr('fill', 'oklch(0.527 0.154 150.069)')
          .attr('font-size', '10px')
          .attr('font-family', 'JetBrains Mono, monospace')
          .text(`TP${i + 1}: $${tp.toFixed(2)}`);
      });
    }

    if (showLevels.orderBlocks) {
      result.orderBlocks.forEach((ob) => {
        const obY = yScale(ob.price);
        const obHeight = 20;
        
        g.append('rect')
          .attr('x', 0)
          .attr('y', obY - obHeight / 2)
          .attr('width', width * 0.3)
          .attr('height', obHeight)
          .attr('fill', ob.type === 'bullish' ? 'oklch(0.75 0.18 140 / 0.15)' : 'oklch(0.704 0.191 22.216 / 0.15)')
          .attr('stroke', ob.type === 'bullish' ? 'oklch(0.75 0.18 140 / 0.5)' : 'oklch(0.704 0.191 22.216 / 0.5)')
          .attr('stroke-width', 1);

        g.append('text')
          .attr('x', 5)
          .attr('y', obY + 4)
          .attr('fill', 'oklch(0.985 0 0 / 0.6)')
          .attr('font-size', '9px')
          .attr('font-family', 'JetBrains Mono, monospace')
          .text(`OB ${ob.type.toUpperCase()}`);
      });
    }

    if (showLevels.fvg) {
      result.fairValueGaps.forEach((fvg) => {
        g.append('rect')
          .attr('x', width * 0.6)
          .attr('y', yScale(fvg.high))
          .attr('width', width * 0.4)
          .attr('height', yScale(fvg.low) - yScale(fvg.high))
          .attr('fill', fvg.type === 'bullish' ? 'oklch(0.75 0.18 140 / 0.08)' : 'oklch(0.704 0.191 22.216 / 0.08)')
          .attr('stroke', fvg.type === 'bullish' ? 'oklch(0.75 0.18 140 / 0.4)' : 'oklch(0.704 0.191 22.216 / 0.4)')
          .attr('stroke-width', 1)
          .attr('stroke-dasharray', '2,2');

        g.append('text')
          .attr('x', width * 0.6 + 5)
          .attr('y', yScale((fvg.high + fvg.low) / 2) + 4)
          .attr('fill', 'oklch(0.985 0 0 / 0.5)')
          .attr('font-size', '9px')
          .attr('font-family', 'JetBrains Mono, monospace')
          .text('FVG');
      });
    }

    const xAxis = d3.axisBottom(xScale)
      .ticks(6)
      .tickFormat(d => {
        const date = d as Date;
        return timeframe === '1D' 
          ? d3.timeFormat('%b %d')(date)
          : d3.timeFormat('%H:%M')(date);
      });

    g.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(xAxis)
      .attr('color', 'oklch(0.556 0 0)')
      .selectAll('text')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', '10px');

    const yAxis = d3.axisRight(yScale)
      .ticks(8)
      .tickFormat(d => `$${(d as number).toFixed(2)}`);

    g.append('g')
      .attr('transform', `translate(${width},0)`)
      .call(yAxis)
      .attr('color', 'oklch(0.556 0 0)')
      .selectAll('text')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', '10px');
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Tabs value={timeframe} onValueChange={setTimeframe}>
          <TabsList className="bg-muted/50">
            <TabsTrigger value="15m">15m</TabsTrigger>
            <TabsTrigger value="1H">1H</TabsTrigger>
            <TabsTrigger value="4H">4H</TabsTrigger>
            <TabsTrigger value="1D">1D</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex gap-2 flex-wrap">
          <Button
            size="sm"
            variant={showLevels.entry ? 'default' : 'outline'}
            onClick={() => setShowLevels(prev => ({ ...prev, entry: !prev.entry }))}
            className="text-xs"
          >
            <Target size={14} />
            Entry
          </Button>
          <Button
            size="sm"
            variant={showLevels.stopLoss ? 'default' : 'outline'}
            onClick={() => setShowLevels(prev => ({ ...prev, stopLoss: !prev.stopLoss }))}
            className="text-xs"
          >
            <TrendDown size={14} />
            Stop Loss
          </Button>
          <Button
            size="sm"
            variant={showLevels.takeProfits ? 'default' : 'outline'}
            onClick={() => setShowLevels(prev => ({ ...prev, takeProfits: !prev.takeProfits }))}
            className="text-xs"
          >
            <TrendUp size={14} />
            Take Profits
          </Button>
          <Button
            size="sm"
            variant={showLevels.orderBlocks ? 'default' : 'outline'}
            onClick={() => setShowLevels(prev => ({ ...prev, orderBlocks: !prev.orderBlocks }))}
            className="text-xs"
          >
            <ArrowsOutLineHorizontal size={14} />
            Order Blocks
          </Button>
          <Button
            size="sm"
            variant={showLevels.fvg ? 'default' : 'outline'}
            onClick={() => setShowLevels(prev => ({ ...prev, fvg: !prev.fvg }))}
            className="text-xs"
          >
            <ChartLine size={14} />
            FVG
          </Button>
        </div>
      </div>

      <div className="bg-card/30 rounded-lg border border-border p-2">
        <div className="flex items-center gap-2 mb-2 px-2">
          <Badge variant="outline" className="bg-accent/20 text-accent border-accent/50 font-bold">
            {result.pair}
          </Badge>
          <span className="text-xs text-muted-foreground font-mono">
            Current: ${result.entryZone.high.toFixed(2)}
          </span>
        </div>
        
        <div ref={containerRef} className="w-full">
          <svg ref={svgRef} className="w-full" />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        <div className="bg-success/10 border border-success/50 rounded p-2">
          <div className="text-muted-foreground mb-1">Risk/Reward</div>
          <div className="font-bold font-mono text-success">
            1:{((result.takeProfits[0] - result.entryZone.high) / (result.entryZone.high - result.stopLoss)).toFixed(2)}
          </div>
        </div>
        <div className="bg-accent/10 border border-accent/50 rounded p-2">
          <div className="text-muted-foreground mb-1">Confidence</div>
          <div className="font-bold font-mono text-accent">{result.confidenceScore.toFixed(0)}%</div>
        </div>
        <div className="bg-card border border-border rounded p-2">
          <div className="text-muted-foreground mb-1">Risk Score</div>
          <div className="font-bold font-mono">{result.riskScore.toFixed(1)}/10</div>
        </div>
        <div className="bg-card border border-border rounded p-2">
          <div className="text-muted-foreground mb-1">Type</div>
          <div className="font-bold font-mono">{result.classification}</div>
        </div>
      </div>
    </div>
  );
}

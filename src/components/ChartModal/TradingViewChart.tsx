import { useEffect, useRef, useState } from 'react';
import type { ScanResult } from '@/utils/mockData';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  TrendUp, 
  TrendDown, 
  Target,
} from '@phosphor-icons/react';
// Overlay removed for now; revisit later
import { useScanner } from '@/context/ScannerContext';

interface TradingViewChartProps {
  result: ScanResult;
}

export function TradingViewChart({ result }: TradingViewChartProps) {
  const { selectedMode } = useScanner();
  const modeName = selectedMode?.name || result.sniper_mode || 'recon';
  // TradingView handles timeframe changes internally; we just set an initial interval.
  const timeframe = '60'; // initial 1H view
  const [showLevels, setShowLevels] = useState({
    entry: true,
    stopLoss: true,
    takeProfits: true,
  });
  const [showOverlay, setShowOverlay] = useState(false);

  // Convert pair format (e.g., "BTC/USDT" -> "BTCUSDT")
  const baseSymbol = result.pair.replace('/', '');
  
  /**
   * Map our symbols to TradingView-compatible format.
   * 
   * TradingView symbol coverage priority:
   * 1. BINANCE spot - best coverage for all pairs
   * 2. BYBIT perpetuals - good for major perps
   * 3. COINBASE - good fallback for majors
   * 
   * Common issues:
   * - Phemex uses different symbol names (e.g., 1000PEPE vs PEPE)
   * - Some altcoins only exist on certain exchanges
   * - Perpetual suffixes vary (.P, PERP, -PERP)
   */
  const getTradingViewSymbol = (): string => {
    // Clean up the symbol - remove perp suffixes and normalize
    let cleanSymbol = baseSymbol
      .replace(/\.P$/i, '')
      .replace(/PERP$/i, '')
      .replace(/-PERP$/i, '')
      .toUpperCase();
    
    // Handle "1000" prefix symbols (Phemex uses these, TradingView doesn't for spot)
    // e.g., 1000PEPEUSDT -> PEPEUSDT on Binance spot
    const has1000Prefix = cleanSymbol.startsWith('1000');
    const spotSymbol = has1000Prefix ? cleanSymbol.replace('1000', '') : cleanSymbol;
    
    // Major pairs that definitely exist on Binance
    const majorPairs = [
      'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
      'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'MATICUSDT',
      'LINKUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'ETCUSDT',
      'NEARUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT', 'INJUSDT',
      'SUIUSDT', 'SEIUSDT', 'TIAUSDT', 'JUPUSDT', 'WIFUSDT',
      'PEPEUSDT', 'SHIBUSDT', 'FLOKIUSDT', 'BONKUSDT', 'ORDIUSDT',
      'RUNEUSDT', 'FTMUSDT', 'AAVEUSDT', 'MKRUSDT', 'SNXUSDT',
      'CRVUSDT', 'LDOUSDT', 'RNDRUSDT', 'GRTUSDT', 'IMXUSDT',
    ];
    
    // Check if it's a known major pair (use Binance spot for reliability)
    if (majorPairs.includes(spotSymbol)) {
      return `BINANCE:${spotSymbol}`;
    }
    
    // For other pairs, try Binance spot first (best coverage)
    // TradingView will show an error if symbol doesn't exist,
    // but Binance spot has the widest altcoin coverage
    return `BINANCE:${spotSymbol}`;
  };
  
  const tradingViewSymbol = getTradingViewSymbol();
  
  // TradingView embed URL with parameters and drawing studies
  const getTradingViewUrl = () => {
    // Keep URL minimal; render trading levels via our SVG overlay instead
    const params = new URLSearchParams({
      symbol: tradingViewSymbol,
      interval: timeframe,
      theme: 'dark',
      style: '1', // Candlestick
      locale: 'en',
      toolbar_bg: '#141416',
      enable_publishing: 'false',
      hide_top_toolbar: 'false',
      hide_legend: 'false',
      save_image: 'false',
      hide_volume: 'false',
      // studies removed due to TradingView errors (cannot_get_metainfo, study inserter failures)
    });
    
    return `https://s.tradingview.com/widgetembed/?${params.toString()}`;
  };

  return (
    <div className="h-full flex flex-col space-y-4">
      <div className="flex items-center justify-end flex-wrap gap-3">
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
          {/* SMC toggles removed */}
          {/* Density selector removed */}
          {/* Overlay toggle disabled */}
        </div>
      </div>

      <div className="bg-card/30 rounded-lg border border-border p-2 flex-1">
        <div className="flex items-center gap-2 mb-2 px-2">
          <Badge variant="outline" className="bg-accent/20 text-accent border-accent/50 font-bold">
            {result.pair}
          </Badge>
          <span className="text-xs text-muted-foreground font-mono">
            {tradingViewSymbol.split(':')[0]}
          </span>
        </div>
        
        {/* Fixed aspect is controlled by parent; keep iframe contained without stretching */}
        <div className="relative w-full h-full rounded-lg overflow-hidden bg-[#141416]">
          <iframe
            key={`${tradingViewSymbol}-${timeframe}`} // Re-render on symbol/timeframe change
            src={getTradingViewUrl()}
            className="absolute inset-0 w-full h-full border-0"
            title={`${result.pair} Chart`}
            allow="clipboard-write"
            allowFullScreen
          />
          {/* SVG overlay removed */}
        </div>
      </div>

      {/* Trading Levels Display */}
      {(showLevels.entry || showLevels.stopLoss || showLevels.takeProfits) && (
        <div className="bg-card/50 rounded-lg border border-border p-4 space-y-3">
          <h4 className="text-sm font-bold text-foreground mb-3">TRADING LEVELS</h4>
          
          {showLevels.entry && (
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground uppercase">Entry Zone</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-success/10 border border-success/50 rounded px-3 py-2">
                  <div className="text-xs text-muted-foreground">High</div>
                  <div className="font-mono text-sm text-success font-bold">
                    ${result.entryZone.high.toFixed(5)}
                  </div>
                </div>
                <div className="flex-1 bg-success/10 border border-success/50 rounded px-3 py-2">
                  <div className="text-xs text-muted-foreground">Low</div>
                  <div className="font-mono text-sm text-success font-bold">
                    ${result.entryZone.low.toFixed(5)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {showLevels.stopLoss && (
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground uppercase">Stop Loss</div>
              <div className="bg-destructive/10 border border-destructive/50 rounded px-3 py-2">
                <div className="font-mono text-sm text-destructive font-bold">
                  ${result.stopLoss.toFixed(5)}
                </div>
              </div>
            </div>
          )}

          {showLevels.takeProfits && (
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground uppercase">Take Profit Targets</div>
              <div className="grid grid-cols-3 gap-2">
                {result.takeProfits.map((tp, i) => (
                  <div key={i} className="bg-accent/10 border border-accent/50 rounded px-3 py-2">
                    <div className="text-xs text-muted-foreground">TP{i + 1}</div>
                    <div className="font-mono text-sm text-accent font-bold">
                      ${tp.toFixed(5)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

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

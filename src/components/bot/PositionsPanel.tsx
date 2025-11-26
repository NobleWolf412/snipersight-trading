/**
 * Positions Panel Component
 * 
 * Displays active trading positions from the bot executor.
 * Shows entry price, current P&L, and position details.
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/utils/api';
import { TrendUp, TrendDown, Target, Clock } from '@phosphor-icons/react';
import { formatDistanceToNow } from 'date-fns';

interface Position {
  symbol: string;
  direction: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  opened_at: string;
}

export function PositionsPanel() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const response = await api.getPositions();
        
        if (response.error) {
          setError(response.error);
          setLoading(false);
          return;
        }

        if (response.data) {
          setPositions(response.data.positions);
        }
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setLoading(false);
      }
    };

    fetchPositions();
    const interval = setInterval(fetchPositions, 5000); // Refresh every 5s
    
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="command-panel card-3d">
        <CardHeader>
          <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
            <Target size={20} weight="bold" className="text-accent" />
            ACTIVE POSITIONS
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-muted-foreground">Loading positions...</div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="command-panel card-3d border-warning/30">
        <CardHeader>
          <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
            <Target size={20} weight="bold" className="text-warning" />
            ACTIVE POSITIONS
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-warning">
            Failed to load positions: {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (positions.length === 0) {
    return (
      <Card className="command-panel card-3d">
        <CardHeader>
          <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
            <Target size={20} weight="bold" className="text-muted-foreground" />
            ACTIVE POSITIONS
            <Badge variant="outline" className="border-muted-foreground/40 text-muted-foreground">
              0
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <Target size={48} weight="thin" className="mx-auto mb-3 opacity-30" />
            <p>No active positions</p>
            <p className="text-xs mt-1">Waiting for trade signals</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="command-panel card-3d">
      <CardHeader>
        <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
          <Target size={20} weight="bold" className="text-accent" />
          ACTIVE POSITIONS
          <Badge variant="outline" className="border-accent/40 text-accent">
            {positions.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {positions.map((position, idx) => {
            const isProfit = position.pnl >= 0;
            const pnlColor = isProfit ? 'text-success' : 'text-destructive';
            const DirectionIcon = position.direction === 'LONG' ? TrendUp : TrendDown;
            const directionColor = position.direction === 'LONG' ? 'text-success' : 'text-destructive';

            return (
              <div
                key={idx}
                className="rounded-lg border border-slate-700/50 bg-black/20 p-4 hover:border-accent/30 transition-all"
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-lg text-slate-200">{position.symbol}</span>
                    <Badge className={`${directionColor} bg-transparent border`}>
                      <DirectionIcon size={12} weight="bold" className="mr-1" />
                      {position.direction}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <div className={`text-lg font-bold ${pnlColor}`}>
                      {isProfit ? '+' : ''}{position.pnl.toFixed(2)} USDT
                    </div>
                    <div className={`text-xs ${pnlColor}`}>
                      {isProfit ? '+' : ''}{position.pnl_pct.toFixed(2)}%
                    </div>
                  </div>
                </div>

                {/* Position Details */}
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-xs text-slate-400 mb-1">Entry</div>
                    <div className="text-sm font-mono text-slate-200">
                      ${position.entry_price.toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 mb-1">Current</div>
                    <div className="text-sm font-mono text-accent">
                      ${position.current_price.toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 mb-1">Quantity</div>
                    <div className="text-sm font-mono text-slate-200">
                      {position.quantity.toFixed(4)}
                    </div>
                  </div>
                </div>

                {/* Time Open */}
                <div className="mt-3 pt-3 border-t border-slate-700/30">
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <Clock size={12} weight="bold" />
                    Opened {formatDistanceToNow(new Date(position.opened_at), { addSuffix: true })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary Footer */}
        <div className="mt-4 pt-4 border-t border-slate-700/30">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="text-center">
              <div className="text-xs text-slate-400 mb-1">Total Positions</div>
              <div className="font-bold text-lg text-accent">{positions.length}</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-slate-400 mb-1">Combined P&L</div>
              <div className={`font-bold text-lg ${
                positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 ? 'text-success' : 'text-destructive'
              }`}>
                {positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 ? '+' : ''}
                {positions.reduce((sum, p) => sum + p.pnl, 0).toFixed(2)} USDT
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

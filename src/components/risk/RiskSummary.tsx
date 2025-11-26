/**
 * Risk Summary Component
 * 
 * Displays real-time risk management metrics from backend risk manager.
 * Shows exposure limits, position counts, and correlation warnings.
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { api } from '@/utils/api';
import { Shield, Warning, CheckCircle, TrendUp } from '@phosphor-icons/react';

interface RiskSummaryData {
  account_balance: number;
  total_exposure: number;
  exposure_pct: number;
  max_exposure_pct: number;
  open_positions: number;
  max_positions: number;
  available_positions: number;
  correlated_exposure: number;
  correlated_exposure_pct: number;
  max_correlated_pct: number;
  risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  warnings: string[];
}

export function RiskSummary() {
  const [riskData, setRiskData] = useState<RiskSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRiskSummary = async () => {
      try {
        const response = await api.getRiskSummary();
        
        if (response.error) {
          setError(response.error);
          setLoading(false);
          return;
        }

        if (response.data) {
          setRiskData(response.data as RiskSummaryData);
        }
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setLoading(false);
      }
    };

    fetchRiskSummary();
    const interval = setInterval(fetchRiskSummary, 10000); // Refresh every 10s
    
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="command-panel card-3d">
        <CardHeader>
          <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
            <Shield size={20} weight="bold" className="text-accent" />
            RISK MANAGEMENT
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-muted-foreground">Loading risk data...</div>
        </CardContent>
      </Card>
    );
  }

  if (error || !riskData) {
    return (
      <Card className="command-panel card-3d border-warning/30">
        <CardHeader>
          <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
            <Shield size={20} weight="bold" className="text-warning" />
            RISK MANAGEMENT
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6">
            <Warning size={32} weight="bold" className="mx-auto mb-2 text-warning" />
            <div className="text-warning">Risk data unavailable</div>
            {error && <div className="text-xs text-muted-foreground mt-1">{error}</div>}
          </div>
        </CardContent>
      </Card>
    );
  }

  const getRiskLevelColor = (level: string) => {
    switch (level) {
      case 'LOW': return 'text-success';
      case 'MODERATE': return 'text-accent';
      case 'HIGH': return 'text-warning';
      case 'CRITICAL': return 'text-destructive';
      default: return 'text-muted-foreground';
    }
  };

  const getRiskLevelBadgeVariant = (level: string) => {
    switch (level) {
      case 'LOW': return 'default';
      case 'MODERATE': return 'secondary';
      case 'HIGH': return 'outline';
      case 'CRITICAL': return 'destructive';
      default: return 'secondary';
    }
  };

  const exposureProgress = (riskData.exposure_pct / riskData.max_exposure_pct) * 100;
  const positionProgress = (riskData.open_positions / riskData.max_positions) * 100;
  const correlatedProgress = riskData.max_correlated_pct > 0 
    ? (riskData.correlated_exposure_pct / riskData.max_correlated_pct) * 100 
    : 0;

  return (
    <Card className="command-panel card-3d">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm tracking-wider heading-hud flex items-center gap-3">
            <Shield size={20} weight="bold" className="text-accent" />
            RISK MANAGEMENT
          </CardTitle>
          <Badge variant={getRiskLevelBadgeVariant(riskData.risk_level)} className={getRiskLevelColor(riskData.risk_level)}>
            {riskData.risk_level}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Account Balance */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="p-3 bg-background/40 rounded-lg border border-border/40">
            <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider">Account Balance</div>
            <div className="font-bold text-lg text-foreground">${riskData.account_balance.toLocaleString()}</div>
          </div>
          <div className="p-3 bg-background/40 rounded-lg border border-border/40">
            <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider">Total Exposure</div>
            <div className="font-bold text-lg text-accent">${riskData.total_exposure.toLocaleString()}</div>
          </div>
        </div>

        {/* Exposure Progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground uppercase tracking-wider">Portfolio Exposure</span>
            <span className={`font-mono ${exposureProgress > 80 ? 'text-warning' : 'text-accent'}`}>
              {riskData.exposure_pct.toFixed(1)}% / {riskData.max_exposure_pct}%
            </span>
          </div>
          <Progress 
            value={exposureProgress} 
            className="h-2"
          />
        </div>

        {/* Position Utilization */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground uppercase tracking-wider">Position Slots</span>
            <span className="font-mono text-accent">
              {riskData.open_positions} / {riskData.max_positions}
            </span>
          </div>
          <Progress 
            value={positionProgress} 
            className="h-2"
          />
        </div>

        {/* Correlated Exposure */}
        {riskData.max_correlated_pct > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground uppercase tracking-wider">Correlated Exposure</span>
              <span className={`font-mono ${correlatedProgress > 80 ? 'text-warning' : 'text-muted-foreground'}`}>
                {riskData.correlated_exposure_pct.toFixed(1)}% / {riskData.max_correlated_pct}%
              </span>
            </div>
            <Progress 
              value={correlatedProgress} 
              className="h-2"
            />
          </div>
        )}

        {/* Warnings */}
        {riskData.warnings && riskData.warnings.length > 0 && (
          <div className="mt-4 space-y-2">
            {riskData.warnings.map((warning, idx) => (
              <div 
                key={idx} 
                className="flex items-start gap-2 p-2 bg-warning/10 border border-warning/30 rounded text-xs"
              >
                <Warning size={14} weight="bold" className="text-warning flex-shrink-0 mt-0.5" />
                <span className="text-warning">{warning}</span>
              </div>
            ))}
          </div>
        )}

        {/* All Clear */}
        {(!riskData.warnings || riskData.warnings.length === 0) && riskData.risk_level === 'LOW' && (
          <div className="flex items-center gap-2 p-2 bg-success/10 border border-success/30 rounded text-xs">
            <CheckCircle size={14} weight="bold" className="text-success" />
            <span className="text-success">All risk parameters within limits</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

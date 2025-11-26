import { Warning, XCircle, TrendDown, Database, Code, Info, ChartLineUp, ChartLineDown, Stack, Target } from '@phosphor-icons/react';
import { Card } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useState } from 'react';

interface ConfluenceFactor {
  name: string;
  score: number;
  weight: number;
  weighted_contribution: number;
  rationale: string;
}

interface RejectionDetail {
  symbol: string;
  reason: string;
  score?: number;
  threshold?: number;
  top_factors?: string[];
  all_factors?: ConfluenceFactor[];
  synergy_bonus?: number;
  conflict_penalty?: number;
  htf_aligned?: boolean;
  btc_impulse_gate?: boolean;
  risk_reward?: number;
}

interface RejectionStats {
  total_rejected: number;
  by_reason: {
    low_confluence?: number;
    no_data?: number;
    risk_validation?: number;
    no_trade_plan?: number;
    errors?: number;
    missing_critical_tf?: number; // Added missing critical timeframe reason
    [key: string]: number | undefined; // Future-proof
  };
  details: {
    low_confluence?: RejectionDetail[];
    no_data?: RejectionDetail[];
    risk_validation?: RejectionDetail[];
    no_trade_plan?: RejectionDetail[];
    errors?: RejectionDetail[];
    missing_critical_tf?: RejectionDetail[]; // Add details list
    [key: string]: RejectionDetail[] | undefined; // Future-proof
  };
}

interface Props {
  rejections: RejectionStats;
  totalScanned: number;
}

const reasonConfig: Record<string, {
  icon: any;
  label: string;
  color: string;
  description: string;
}> = {
  low_confluence: {
    icon: TrendDown,
    label: 'Low Confluence Score',
    color: 'text-yellow-400',
    description: 'Setup didn\'t meet minimum quality threshold',
  },
  no_data: {
    icon: Database,
    label: 'No Market Data',
    color: 'text-red-400',
    description: 'Unable to fetch price data from exchange',
  },
  risk_validation: {
    icon: Warning,
    label: 'Risk Validation Failed',
    color: 'text-orange-400',
    description: 'Risk/reward ratio below minimum (1.5:1)',
  },
  no_trade_plan: {
    icon: XCircle,
    label: 'No Trade Plan',
    color: 'text-red-400',
    description: 'Insufficient SMC patterns for entry/stop placement',
  },
  errors: {
    icon: Code,
    label: 'Processing Errors',
    color: 'text-red-500',
    description: 'Technical errors during analysis',
  },
  missing_critical_tf: {
    icon: Stack,
    label: 'Missing Critical Timeframes',
    color: 'text-purple-400',
    description: 'Required higher timeframe data unavailable or incomplete',
  },
};

export function RejectionSummary({ rejections, totalScanned }: Props) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);
  // Dialog for category-level aggregated view
  const [reasonDialog, setReasonDialog] = useState<string | null>(null);

  if (!rejections || !rejections.total_rejected || rejections.total_rejected === 0) {
    return null;
  }

  const rejectionPercentage = ((rejections.total_rejected / totalScanned) * 100).toFixed(1);
  
  // Safety check for by_reason and details
  const byReason = rejections.by_reason || {};
  const details = rejections.details || {};

  return (
    <Card className="tactical-card p-6">
      <div className="flex items-start gap-4 mb-6">
        <div className="p-3 rounded-lg bg-yellow-500/10">
          <Warning className="w-6 h-6 text-yellow-400" weight="duotone" />
        </div>
        <div className="flex-1">
          <h3 className="heading-hud text-lg mb-1">Rejection Analysis</h3>
          <p className="text-sm text-muted-foreground">
            {rejections.total_rejected} / {totalScanned} symbols rejected ({rejectionPercentage}%)
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {Object.entries(byReason).map(([reason, count]) => {
          if (count === 0) return null;

          const config = reasonConfig[reason] || {
            icon: Info,
            label: reason.replace(/_/g, ' '),
            color: 'text-muted-foreground',
            description: 'Additional rejection category',
          };
          
          const Icon = config.icon;
          const reasonDetails = details[reason as keyof typeof details] || [];
          const isExpanded = expandedSection === reason;

          return (
            <Collapsible
              key={reason}
              open={isExpanded}
              onOpenChange={() => setExpandedSection(isExpanded ? null : reason)}
            >
              <CollapsibleTrigger className="w-full">
                <div className="flex items-center gap-3 p-3 rounded-lg bg-card/50 hover:bg-card/70 transition-colors cursor-pointer">
                  <Icon className={`w-5 h-5 ${config.color}`} weight="duotone" />
                  <div className="flex-1 text-left">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{config.label}</span>
                      <span className="text-xs font-mono text-muted-foreground">{count}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{config.description}</p>
                  </div>
                  {Array.isArray(reasonDetails) && reasonDetails.length > 0 && (
                    <Dialog open={reasonDialog === reason} onOpenChange={(open) => !open && setReasonDialog(null)}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setReasonDialog(reason);
                        }}
                      >
                        <Info className="w-3 h-3 mr-1" /> View All
                      </Button>
                      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2">
                            <Icon className={`w-5 h-5 ${config.color}`} />
                            {config.label} – {reasonDetails.length} Rejections
                          </DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                          {reasonDetails.map((detail, idx) => (
                            <Card key={idx} className="p-3 bg-background/40 border border-border/50">
                              <div className="flex items-center justify-between mb-2">
                                <div className="font-mono text-primary font-medium">{detail.symbol}</div>
                                {detail.score !== undefined && detail.threshold !== undefined && (
                                  <Badge variant="secondary" className="font-mono text-xs">
                                    {detail.score.toFixed(1)} / {detail.threshold.toFixed(1)}
                                  </Badge>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground mb-2">{detail.reason}</div>
                              {detail.all_factors && detail.all_factors.length > 0 && (
                                <div className="grid grid-cols-2 gap-2">
                                  {detail.all_factors.slice(0, 4).map((f, fIdx) => (
                                    <div key={fIdx} className="text-xxs p-2 rounded bg-card/30 border border-border/40">
                                      <div className="flex items-center justify-between mb-1">
                                        <span className="text-[10px] font-medium truncate max-w-[70%]">{f.name}</span>
                                        <span className="font-mono text-[10px] text-muted-foreground">{f.score.toFixed(0)}%</span>
                                      </div>
                                      <Progress value={f.score} className="h-1" />
                                    </div>
                                  ))}
                                </div>
                              )}
                            </Card>
                          ))}
                          {reasonDetails.length > 12 && (
                            <div className="text-xs text-muted-foreground text-center">
                              Showing {reasonDetails.length} rejections
                            </div>
                          )}
                        </div>
                      </DialogContent>
                    </Dialog>
                  )}
                </div>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <div className="mt-2 ml-8 space-y-2">
                  {Array.isArray(reasonDetails) && reasonDetails.slice(0, 10).map((detail, idx) => (
                    <Dialog key={idx}>
                      <DialogTrigger asChild>
                        <div className="p-3 rounded bg-background/50 border border-border/50 hover:border-primary/50 cursor-pointer transition-colors">
                          <div className="flex items-center justify-between mb-2">
                            <div className="font-mono text-primary font-medium">{detail.symbol}</div>
                            <Button variant="ghost" size="sm" className="h-6 text-xs">
                              <Info className="w-3 h-3 mr-1" />
                              Details
                            </Button>
                          </div>
                          <div className="text-xs text-muted-foreground">{detail.reason}</div>
                          {detail.score !== undefined && detail.threshold !== undefined && (
                            <div className="mt-2">
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-yellow-400">Score: {detail.score.toFixed(1)}%</span>
                                <span className="text-muted-foreground">Threshold: {detail.threshold.toFixed(1)}%</span>
                              </div>
                              <Progress value={(detail.score / detail.threshold) * 100} className="h-1" />
                            </div>
                          )}
                          {detail.risk_reward !== undefined && (
                            <div className="mt-2 text-xs text-orange-400">
                              Risk/Reward: {detail.risk_reward.toFixed(2)}:1
                            </div>
                          )}
                        </div>
                      </DialogTrigger>
                      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2">
                            <TrendDown className="w-5 h-5 text-yellow-400" />
                            Rejection Analysis: {detail.symbol}
                          </DialogTitle>
                        </DialogHeader>
                        
                        <div className="space-y-6">
                          {/* Summary */}
                          <Card className="p-4 bg-card/50">
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <div className="text-xs text-muted-foreground mb-1">Rejection Reason</div>
                                <div className="text-sm font-medium">{detail.reason}</div>
                              </div>
                              {detail.score !== undefined && detail.threshold !== undefined && (
                                <div>
                                  <div className="text-xs text-muted-foreground mb-1">Confluence Score</div>
                                  <div className="text-lg font-mono">
                                    <span className="text-yellow-400">{detail.score.toFixed(1)}%</span>
                                    <span className="text-muted-foreground mx-2">/</span>
                                    <span className="text-foreground">{detail.threshold.toFixed(1)}%</span>
                                    <span className="text-xs ml-2 text-red-400">
                                      ({(detail.score - detail.threshold).toFixed(1)}%)
                                    </span>
                                  </div>
                                </div>
                              )}
                            </div>
                          </Card>

                          {/* Confluence Factors */}
                          {detail.all_factors && detail.all_factors.length > 0 && (
                            <div>
                              <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                                <Stack className="w-4 h-4" />
                                Confluence Factor Breakdown
                              </h4>
                              <div className="space-y-3">
                                {detail.all_factors.map((factor, fIdx) => {
                                  const isStrong = factor.score >= 70;
                                  const isWeak = factor.score < 40;
                                  const contributionPct = (factor.weighted_contribution / (detail.score || 1)) * 100;
                                  
                                  return (
                                    <Card key={fIdx} className={`p-3 ${
                                      isStrong ? 'border-green-500/30 bg-green-500/5' :
                                      isWeak ? 'border-red-500/30 bg-red-500/5' :
                                      'border-border/50 bg-card/30'
                                    }`}>
                                      <div className="flex items-start justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                          <div className="text-sm font-medium">{factor.name}</div>
                                          <Badge variant={isStrong ? 'default' : isWeak ? 'destructive' : 'secondary'} className="text-xs">
                                            {factor.score.toFixed(1)}%
                                          </Badge>
                                        </div>
                                        <div className="text-xs text-muted-foreground">
                                          Weight: {(factor.weight * 100).toFixed(0)}%
                                        </div>
                                      </div>
                                      
                                      <Progress value={factor.score} className="h-2 mb-2" />
                                      
                                      <div className="text-xs text-muted-foreground mb-2">
                                        {factor.rationale}
                                      </div>
                                      
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="text-muted-foreground">
                                          Contribution to total score:
                                        </span>
                                        <span className="font-mono text-primary">
                                          {factor.weighted_contribution.toFixed(1)}% ({contributionPct.toFixed(0)}% of total)
                                        </span>
                                      </div>
                                    </Card>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Bonuses & Penalties */}
                          {(detail.synergy_bonus !== undefined || detail.conflict_penalty !== undefined) && (
                            <div className="grid grid-cols-2 gap-4">
                              {detail.synergy_bonus !== undefined && detail.synergy_bonus > 0 && (
                                <Card className="p-3 border-green-500/30 bg-green-500/5">
                                  <div className="flex items-center gap-2 mb-1">
                                    <ChartLineUp className="w-4 h-4 text-green-400" />
                                    <span className="text-sm font-medium">Synergy Bonus</span>
                                  </div>
                                  <div className="text-lg font-mono text-green-400">
                                    +{detail.synergy_bonus.toFixed(1)}%
                                  </div>
                                  <div className="text-xs text-muted-foreground mt-1">
                                    Multiple factors aligned
                                  </div>
                                </Card>
                              )}
                              
                              {detail.conflict_penalty !== undefined && detail.conflict_penalty > 0 && (
                                <Card className="p-3 border-red-500/30 bg-red-500/5">
                                  <div className="flex items-center gap-2 mb-1">
                                    <ChartLineDown className="w-4 h-4 text-red-400" />
                                    <span className="text-sm font-medium">Conflict Penalty</span>
                                  </div>
                                  <div className="text-lg font-mono text-red-400">
                                    -{detail.conflict_penalty.toFixed(1)}%
                                  </div>
                                  <div className="text-xs text-muted-foreground mt-1">
                                    Conflicting signals detected
                                  </div>
                                </Card>
                              )}
                            </div>
                          )}

                          {/* Context Flags */}
                          <div className="flex gap-3">
                            {detail.htf_aligned !== undefined && (
                              <Badge variant={detail.htf_aligned ? 'default' : 'secondary'} className="text-xs">
                                <Target className="w-3 h-3 mr-1" />
                                HTF {detail.htf_aligned ? 'Aligned' : 'Not Aligned'}
                              </Badge>
                            )}
                            {detail.btc_impulse_gate !== undefined && (
                              <Badge variant={detail.btc_impulse_gate ? 'default' : 'destructive'} className="text-xs">
                                BTC Gate {detail.btc_impulse_gate ? 'Passed' : 'Failed'}
                              </Badge>
                            )}
                          </div>

                          {/* Problem Areas */}
                          {detail.all_factors && (
                            <div>
                              <h4 className="text-sm font-semibold mb-3 text-red-400">Key Problem Areas</h4>
                              <div className="space-y-2">
                                {detail.all_factors
                                  .filter(f => f.score < 50)
                                  .sort((a, b) => a.score - b.score)
                                  .map((factor, idx) => (
                                    <div key={idx} className="text-xs p-2 rounded bg-red-500/10 border border-red-500/20">
                                      <span className="font-medium text-red-400">{factor.name}</span>
                                      <span className="text-muted-foreground ml-2">({factor.score.toFixed(1)}%)</span>
                                      <div className="text-muted-foreground mt-1">{factor.rationale}</div>
                                    </div>
                                  ))}
                                {detail.all_factors.filter(f => f.score < 50).length === 0 && (
                                  <div className="text-xs text-muted-foreground italic">
                                    No weak factors - rejection due to overall score below threshold
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </DialogContent>
                    </Dialog>
                  ))}
                  {Array.isArray(reasonDetails) && reasonDetails.length > 10 && (
                    <div className="text-xs text-center text-muted-foreground pt-2">
                      +{reasonDetails.length - 10} more rejections...
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </div>

      <div className="mt-4 pt-4 border-t border-border/50">
        <p className="text-xs text-muted-foreground">
          💡 <strong>Tip:</strong> Try lowering the mode threshold or switching to a different mode (Strike, Recon, Ghost) for more signals.
        </p>
      </div>
    </Card>
  );
}

import { Warning, XCircle, TrendDown, Database, Code, Info, ChartLineUp, ChartLineDown, Stack, Target } from '@phosphor-icons/react';
import { Card } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useState } from 'react';
import { TargetIntelScorecard } from '@/components/TargetIntelScorecard/TargetIntelScorecard';
import { ConfluenceBreakdown, ConfluenceFactor } from '@/types/confluence';

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

interface DirectionStats {
  longs_generated: number;
  shorts_generated: number;
  tie_breaks_long: number;
  tie_breaks_short: number;
  tie_breaks_neutral_default: number;
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
  direction_stats?: DirectionStats; // Direction analytics tracking
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

// Helper: Convert RejectionDetail to valid ConfluenceBreakdown for Scorecard
const transformToBreakdown = (detail: RejectionDetail): ConfluenceBreakdown => {
  return {
    total_score: detail.score || 0,
    synergy_bonus: detail.synergy_bonus || 0,
    conflict_penalty: detail.conflict_penalty || 0,
    regime: 'unknown', // Rejection summaries might not capture regime string
    htf_aligned: detail.htf_aligned || false,
    btc_impulse_gate: detail.btc_impulse_gate || false,
    factors: detail.all_factors || []
  };
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
              <div className="flex items-center gap-2">
                <CollapsibleTrigger className="flex-1">
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-card/50 hover:bg-card/70 transition-colors cursor-pointer">
                    <Icon className={`w-5 h-5 ${config.color}`} weight="duotone" />
                    <div className="flex-1 text-left">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{config.label}</span>
                        <span className="text-xs font-mono text-muted-foreground">{count}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{config.description}</p>
                    </div>
                  </div>
                </CollapsibleTrigger>
                {Array.isArray(reasonDetails) && reasonDetails.length > 0 && (
                  <Dialog open={reasonDialog === reason} onOpenChange={(open) => !open && setReasonDialog(null)}>
                    <DialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs mr-2"
                        onClick={(e) => {
                          e.stopPropagation();
                          setReasonDialog(reason);
                        }}
                      >
                        <Info className="w-3 h-3 mr-1" /> View All
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="w-full max-w-3xl max-h-[80vh] overflow-y-auto overflow-x-hidden">
                      <DialogHeader>
                        <div className="flex items-center justify-between">
                          <DialogTitle className="flex items-center gap-2">
                            <Icon className={`w-5 h-5 ${config.color}`} />
                            {config.label} – {reasonDetails.length} Rejections
                          </DialogTitle>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setReasonDialog(null)}
                            className="text-xs"
                          >
                            Close
                          </Button>
                        </div>
                        <DialogDescription className="text-sm text-muted-foreground">
                          Detailed breakdown of all {reasonDetails.length} symbols rejected for {config.label.toLowerCase()}
                        </DialogDescription>
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
                            {/* Reuse TargetIntelScorecard for consistent visualization */}
                            {detail.all_factors && detail.all_factors.length > 0 ? (
                              <div className="mt-2 text-xs">
                                <TargetIntelScorecard breakdown={transformToBreakdown(detail)} />
                              </div>
                            ) : (
                              /* Fallback for non-score reasons (like No Data or Errors) */
                              <div className="text-xs text-muted-foreground italic pl-2 border-l-2 border-border">
                                Detailed scoring analysis not available for this rejection type.
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

              <CollapsibleContent>
                <div className="mt-2 ml-8 space-y-2">
                  {Array.isArray(reasonDetails) && reasonDetails.slice(0, 10).map((detail, idx) => (
                    <Dialog key={idx}>
                      <DialogTrigger asChild>
                        <div
                          className="p-3 rounded bg-background/50 border border-border/50 hover:border-primary/50 cursor-pointer transition-colors"
                          role="button"
                          tabIndex={0}
                          aria-label={`View details for ${detail.symbol}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="font-mono text-primary font-medium">{detail.symbol}</div>
                            <div className="text-xs text-primary flex items-center gap-1">
                              <Info className="w-3 h-3" />
                              Details
                            </div>
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
                      <DialogContent className="w-full max-w-3xl max-h-[80vh] overflow-y-auto overflow-x-hidden">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2">
                            <TrendDown className="w-5 h-5 text-yellow-400" />
                            Rejection Analysis: {detail.symbol}
                          </DialogTitle>
                          <DialogDescription className="text-sm text-muted-foreground">
                            Detailed confluence factor breakdown and rejection rationale for {detail.symbol}
                          </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-6 pt-2">
                          {/* Summary Card */}
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

                          {/* REPLACED MANUAL RENDERING WITH TARGET INTEL SCORECARD */}
                          {detail.all_factors && detail.all_factors.length > 0 ? (
                            <TargetIntelScorecard breakdown={transformToBreakdown(detail)} />
                          ) : (
                            <div className="text-center text-muted-foreground text-sm py-4">
                              No detailed factor breakdown available.
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

      {/* Direction Analytics - shows signal distribution */}
      {rejections.direction_stats && (rejections.direction_stats.longs_generated > 0 || rejections.direction_stats.shorts_generated > 0) && (
        <div className="mt-4 pt-4 border-t border-border/50">
          <h4 className="text-xs font-semibold mb-3 flex items-center gap-2 text-muted-foreground uppercase tracking-wider">
            <Target className="w-4 h-4" />
            Direction Analytics
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
              <div className="flex items-center gap-2 mb-1">
                <ChartLineUp className="w-4 h-4 text-green-400" />
                <span className="text-xs text-muted-foreground">Longs</span>
              </div>
              <div className="text-lg font-mono font-bold text-green-400">
                {rejections.direction_stats.longs_generated}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <div className="flex items-center gap-2 mb-1">
                <ChartLineDown className="w-4 h-4 text-red-400" />
                <span className="text-xs text-muted-foreground">Shorts</span>
              </div>
              <div className="text-lg font-mono font-bold text-red-400">
                {rejections.direction_stats.shorts_generated}
              </div>
            </div>
            {(rejections.direction_stats.tie_breaks_long > 0 || rejections.direction_stats.tie_breaks_short > 0 || rejections.direction_stats.tie_breaks_neutral_default > 0) && (
              <>
                <div className="p-3 rounded-lg bg-accent/10 border border-accent/20 col-span-2 md:col-span-2">
                  <div className="text-xs text-muted-foreground mb-2">Tie-Break Resolution</div>
                  <div className="flex items-center gap-4 text-xs">
                    {rejections.direction_stats.tie_breaks_long > 0 && (
                      <span className="text-green-400">
                        Regime→Long: {rejections.direction_stats.tie_breaks_long}
                      </span>
                    )}
                    {rejections.direction_stats.tie_breaks_short > 0 && (
                      <span className="text-red-400">
                        Regime→Short: {rejections.direction_stats.tie_breaks_short}
                      </span>
                    )}
                    {rejections.direction_stats.tie_breaks_neutral_default > 0 && (
                      <span className="text-yellow-400">
                        Neutral→Long: {rejections.direction_stats.tie_breaks_neutral_default}
                      </span>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-border/50">
        <p className="text-xs text-muted-foreground">
          💡 <strong>Tip:</strong> Try lowering the mode threshold or switching to a different mode (Strike, Recon, Ghost) for more signals.
        </p>
      </div>
    </Card>
  );
}

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
import { ScrollArea } from '@/components/ui/scroll-area';
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
  defaultCollapsed?: boolean;
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

// Helper: Get improvement suggestion based on rejection reason and factors
const getSuggestion = (reason: string, detail: RejectionDetail): string => {
  // Find weakest factors if available
  const weakFactors = detail.all_factors
    ?.filter(f => f.score < 50)
    ?.map(f => f.name.replace(/_/g, ' '))
    ?.slice(0, 2) || [];

  if (reason === 'low_confluence') {
    if (weakFactors.length > 0) {
      return `Needs better ${weakFactors.join(' and ')}`;
    }
    const gap = ((detail.threshold || 0) - (detail.score || 0));
    if (gap < 3) return 'Very close - may pass on rescan';
    if (gap < 7) return 'Needs MTF alignment or OB confirmation';
    return 'Multiple factors need improvement';
  }
  if (reason === 'no_trade_plan') {
    if (detail.reason?.includes('stop')) return 'Stop too tight for ATR';
    if (detail.reason?.includes('OB') || detail.reason?.includes('order block')) return 'No valid Order Block found';
    return 'Entry/stop structure missing';
  }
  if (reason === 'risk_validation') {
    return `R:R ${detail.risk_reward?.toFixed(1) || 'N/A'}:1 - needs wider target`;
  }
  if (reason === 'no_data') {
    return 'Price data unavailable - try later';
  }
  return 'Check factors in detail view';
};

// Helper: Get mode suggestion for capturing rejected signals
const getModeSuggestion = (reason: string, threshold?: number): { action: string; mode: string } => {
  if (reason === 'low_confluence') {
    if (threshold && threshold >= 70) {
      return { action: 'Lower threshold to 65%', mode: 'STRIKE' };
    }
    return { action: 'Try exploration mode', mode: 'RECON' };
  }
  if (reason === 'no_trade_plan') {
    return { action: 'For tighter entries', mode: 'SURGICAL' };
  }
  return { action: '', mode: '' };
};

export function RejectionSummary({ rejections, totalScanned, defaultCollapsed = false }: Props) {
  const [expandedSection, setExpandedSection] = useState<string | null>(defaultCollapsed ? null : 'main');
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
                    <DialogContent className="w-full max-w-[95vw] lg:max-w-[85vw] h-[85vh] flex flex-col p-0 gap-0 overflow-hidden">
                      <DialogHeader className="p-4 sm:p-6 border-b border-border/50 shrink-0">
                        <div className="flex items-center justify-between gap-4">
                          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg">
                            <Icon className={`w-5 h-5 ${config.color} shrink-0`} />
                            <span className="truncate">{config.label}</span>
                            <Badge variant="secondary" className="font-mono text-xs shrink-0">
                              {reasonDetails.length}
                            </Badge>
                          </DialogTitle>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setReasonDialog(null)}
                            className="text-xs shrink-0"
                          >
                            Close
                          </Button>
                        </div>
                        <DialogDescription className="text-xs sm:text-sm text-muted-foreground mt-1">
                          Detailed breakdown of all {reasonDetails.length} symbols rejected for {config.label.toLowerCase()}
                        </DialogDescription>
                      </DialogHeader>
                      <ScrollArea className="flex-1 overflow-auto">
                        <div className="p-4 sm:p-6">
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3 sm:gap-4">
                            {reasonDetails.map((detail, idx) => (
                              <Card
                                key={idx}
                                className="p-3 sm:p-4 bg-background/60 border border-border/50 hover:border-primary/30 transition-colors flex flex-col"
                              >
                                {/* Header: Symbol + Score */}
                                <div className="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-border/30">
                                  <span className="font-mono text-primary font-semibold text-sm truncate">
                                    {detail.symbol.replace(':USDT', '')}
                                  </span>
                                  {detail.score !== undefined && detail.threshold !== undefined && (
                                    <Badge
                                      variant={detail.score >= detail.threshold * 0.9 ? "default" : "secondary"}
                                      className="font-mono text-xs shrink-0"
                                    >
                                      {detail.score.toFixed(1)}%
                                    </Badge>
                                  )}
                                </div>

                                {/* Progress Bar */}
                                {detail.score !== undefined && detail.threshold !== undefined && (
                                  <div className="mb-3">
                                    <div className="flex items-center justify-between text-[10px] mb-1 text-muted-foreground">
                                      <span>Score</span>
                                      <span>{detail.score.toFixed(1)} / {detail.threshold.toFixed(1)}</span>
                                    </div>
                                    <Progress
                                      value={(detail.score / detail.threshold) * 100}
                                      className="h-1.5"
                                    />
                                  </div>
                                )}

                                {/* All Factors - Scrollable List */}
                                {detail.all_factors && detail.all_factors.length > 0 && (
                                  <div className="flex-1 overflow-hidden">
                                    <div className="max-h-48 overflow-y-auto pr-1 space-y-2">
                                      {detail.all_factors.map((factor, fidx) => (
                                        <div key={fidx} className="flex items-center justify-between gap-3">
                                          <span className="text-muted-foreground text-sm leading-tight flex-1">
                                            {factor.name.replace(/_/g, ' ')}
                                          </span>
                                          <span className={`font-mono text-sm font-medium shrink-0 ${factor.score >= 70 ? 'text-green-400' :
                                            factor.score >= 50 ? 'text-yellow-400' :
                                              'text-red-400'
                                            }`}>
                                            {factor.score.toFixed(0)}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Fallback for non-score rejections */}
                                {(!detail.all_factors || detail.all_factors.length === 0) && (
                                  <p className="text-xs text-muted-foreground/70 italic flex-1">
                                    {detail.reason}
                                  </p>
                                )}
                              </Card>
                            ))}
                          </div>
                        </div>
                      </ScrollArea>
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
                            <div className="flex items-center gap-2">
                              {detail.score !== undefined && detail.threshold !== undefined && (
                                <Badge
                                  variant="outline"
                                  className={`font-mono text-[10px] ${(detail.threshold - detail.score) < 3
                                    ? 'text-yellow-400 border-yellow-400/50'
                                    : 'text-red-400 border-red-400/50'
                                    }`}
                                >
                                  Gap: {(detail.threshold - detail.score).toFixed(1)}%
                                </Badge>
                              )}
                              <div className="text-xs text-primary flex items-center gap-1">
                                <Info className="w-3 h-3" />
                                Details
                              </div>
                            </div>
                          </div>
                          {/* Score row */}
                          {detail.score !== undefined && detail.threshold !== undefined && (
                            <div className="mb-2">
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-yellow-400">Score: {detail.score.toFixed(1)}%</span>
                                <span className="text-muted-foreground">Threshold: {detail.threshold.toFixed(1)}%</span>
                              </div>
                              <Progress value={(detail.score / detail.threshold) * 100} className="h-1" />
                            </div>
                          )}
                          {/* Suggestion */}
                          <div className="text-xs text-muted-foreground italic">
                            💡 {getSuggestion(reason, detail)}
                          </div>
                          {detail.risk_reward !== undefined && (
                            <div className="mt-2 text-xs text-orange-400">
                              Risk/Reward: {detail.risk_reward.toFixed(2)}:1
                            </div>
                          )}
                        </div>
                      </DialogTrigger>
                      <DialogContent className="w-full max-w-5xl max-h-[85vh] overflow-y-auto overflow-x-hidden">
                        <DialogHeader className="pb-4 border-b border-border/30">
                          <DialogTitle className="flex items-center gap-3 text-xl">
                            <TrendDown className="w-6 h-6 text-yellow-400" />
                            Rejection Analysis: {detail.symbol}
                          </DialogTitle>
                          <DialogDescription className="text-sm text-muted-foreground mt-1">
                            Detailed confluence factor breakdown and rejection rationale for {detail.symbol}
                          </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-6 pt-6">
                          {/* Summary Card */}
                          <Card className="p-5 bg-card/50 border border-border/50">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                              <div>
                                <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Rejection Reason</div>
                                <p className="text-sm font-medium leading-relaxed break-words">{detail.reason}</p>
                              </div>
                              {detail.score !== undefined && detail.threshold !== undefined && (
                                <div>
                                  <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Confluence Score</div>
                                  <div className="text-2xl font-mono font-semibold">
                                    <span className="text-yellow-400">{detail.score.toFixed(1)}%</span>
                                    <span className="text-muted-foreground mx-2">/</span>
                                    <span className="text-foreground">{detail.threshold.toFixed(1)}%</span>
                                    <span className="text-sm ml-3 text-red-400 font-normal">
                                      ({(detail.score - detail.threshold).toFixed(1)}% below threshold)
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
                  {/* Mode suggestion for capturing these */}
                  {(() => {
                    const suggestion = getModeSuggestion(reason, reasonDetails[0]?.threshold);
                    if (!suggestion.mode) return null;
                    return (
                      <div className="mt-3 p-3 rounded-lg bg-accent/10 border border-accent/30">
                        <div className="text-xs text-accent">
                          💡 <strong>How to capture these:</strong> {suggestion.action} with{' '}
                          <Badge className="bg-accent/20 text-accent text-[10px] ml-1">
                            {suggestion.mode}
                          </Badge>{' '}
                          mode
                        </div>
                      </div>
                    );
                  })()}
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

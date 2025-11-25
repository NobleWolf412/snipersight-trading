import { AlertTriangle, XCircle, TrendingDown, Database, Code } from '@phosphor-icons/react';
import { Card } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { useState } from 'react';

interface RejectionDetail {
  symbol: string;
  reason: string;
  score?: number;
  threshold?: number;
  top_factors?: string[];
  risk_reward?: number;
}

interface RejectionStats {
  total_rejected: number;
  by_reason: {
    low_confluence: number;
    no_data: number;
    risk_validation: number;
    no_trade_plan: number;
    errors: number;
  };
  details: {
    low_confluence: RejectionDetail[];
    no_data: RejectionDetail[];
    risk_validation: RejectionDetail[];
    no_trade_plan: RejectionDetail[];
    errors: RejectionDetail[];
  };
}

interface Props {
  rejections: RejectionStats;
  totalScanned: number;
}

const reasonConfig = {
  low_confluence: {
    icon: TrendingDown,
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
    icon: AlertTriangle,
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
};

export function RejectionSummary({ rejections, totalScanned }: Props) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  if (!rejections || rejections.total_rejected === 0) {
    return null;
  }

  const rejectionPercentage = ((rejections.total_rejected / totalScanned) * 100).toFixed(1);

  return (
    <Card className="tactical-card p-6">
      <div className="flex items-start gap-4 mb-6">
        <div className="p-3 rounded-lg bg-yellow-500/10">
          <AlertTriangle className="w-6 h-6 text-yellow-400" weight="duotone" />
        </div>
        <div className="flex-1">
          <h3 className="heading-hud text-lg mb-1">Rejection Analysis</h3>
          <p className="text-sm text-muted-foreground">
            {rejections.total_rejected} / {totalScanned} symbols rejected ({rejectionPercentage}%)
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {Object.entries(rejections.by_reason).map(([reason, count]) => {
          if (count === 0) return null;

          const config = reasonConfig[reason as keyof typeof reasonConfig];
          const Icon = config.icon;
          const details = rejections.details[reason as keyof typeof rejections.details] || [];
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
                </div>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <div className="mt-2 ml-8 space-y-2">
                  {details.slice(0, 5).map((detail, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded bg-background/50 border border-border/50 text-xs"
                    >
                      <div className="font-mono text-primary mb-1">{detail.symbol}</div>
                      <div className="text-muted-foreground">{detail.reason}</div>
                      {detail.score !== undefined && detail.threshold !== undefined && (
                        <div className="mt-1 text-yellow-400">
                          Score: {detail.score.toFixed(1)} / {detail.threshold.toFixed(1)}
                        </div>
                      )}
                      {detail.top_factors && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          Top factors: {detail.top_factors.join(', ')}
                        </div>
                      )}
                      {detail.risk_reward !== undefined && (
                        <div className="mt-1 text-orange-400">
                          R:R: {detail.risk_reward.toFixed(2)}
                        </div>
                      )}
                    </div>
                  ))}
                  {details.length > 5 && (
                    <div className="text-xs text-center text-muted-foreground pt-2">
                      +{details.length - 5} more...
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

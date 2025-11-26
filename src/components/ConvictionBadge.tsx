/**
 * ConvictionBadge Component
 * 
 * Displays signal conviction class (A/B/C) with plan type indicator
 */

import { PlanType, ConvictionClass } from '@/types/regime';
import { Shield, ShieldAlert, ShieldCheck, Target } from 'lucide-react';

interface ConvictionBadgeProps {
  conviction: ConvictionClass;
  planType: PlanType;
  size?: 'sm' | 'md' | 'lg';
  showPlanType?: boolean;
}

export function ConvictionBadge({ 
  conviction, 
  planType, 
  size = 'md',
  showPlanType = true 
}: ConvictionBadgeProps) {
  const styles = getConvictionStyles(conviction);
  const iconSize = size === 'sm' ? 12 : size === 'lg' ? 18 : 14;
  
  return (
    <div className="flex items-center gap-1.5">
      <div className={`
        flex items-center gap-1 px-2 py-0.5 rounded
        ${styles.bg} ${styles.border} ${styles.text}
        ${size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-base' : 'text-sm'}
        font-semibold
      `}>
        {conviction === 'A' && <ShieldCheck size={iconSize} />}
        {conviction === 'B' && <Shield size={iconSize} />}
        {conviction === 'C' && <ShieldAlert size={iconSize} />}
        <span>Class {conviction}</span>
      </div>
      
      {showPlanType && (
        <div className={`
          flex items-center gap-1 px-1.5 py-0.5 rounded
          ${getPlanTypeStyles(planType).bg}
          ${size === 'sm' ? 'text-xs' : 'text-xs'}
          font-mono text-muted-foreground
        `}>
          <Target size={10} />
          <span>{planType}</span>
        </div>
      )}
    </div>
  );
}

function getConvictionStyles(conviction: ConvictionClass) {
  switch (conviction) {
    case 'A':
      return {
        bg: 'bg-green-500/10',
        border: 'border border-green-500/30',
        text: 'text-green-500'
      };
    case 'B':
      return {
        bg: 'bg-blue-500/10',
        border: 'border border-blue-500/30',
        text: 'text-blue-500'
      };
    case 'C':
      return {
        bg: 'bg-yellow-500/10',
        border: 'border border-yellow-500/30',
        text: 'text-yellow-500'
      };
  }
}

function getPlanTypeStyles(planType: PlanType) {
  switch (planType) {
    case 'SMC':
      return { bg: 'bg-accent/20' };
    case 'HYBRID':
      return { bg: 'bg-primary/20' };
    case 'ATR_FALLBACK':
      return { bg: 'bg-muted/40' };
  }
}

// Conviction description for tooltips/info
export function getConvictionDescription(conviction: ConvictionClass, planType: PlanType): string {
  const base = {
    A: 'Ideal conditions: SMC structure + high R:R + strong confluence + all critical timeframes',
    B: 'Good quality: Solid structure or strong metrics, most criteria met',
    C: 'Acceptable: May use ATR fallback, lower R:R, or missing some timeframes'
  }[conviction];
  
  const planInfo = {
    SMC: 'Structure-based entry & stop (Order Blocks, FVGs)',
    HYBRID: 'Mixed: Some structure, some ATR components',
    ATR_FALLBACK: 'ATR-based entry/stop (no clear SMC structure)'
  }[planType];
  
  return `${base}\n\nPlan: ${planInfo}`;
}

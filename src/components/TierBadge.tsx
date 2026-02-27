import { Star } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { getSignalTier, type SignalTier } from '@/utils/signalTiers';

interface TierBadgeProps {
    confidenceScore: number;
    size?: 'sm' | 'md';
    showLabel?: boolean;
}

/**
 * TierBadge - Shows quality tier for a signal (TOP/HIGH/SOLID)
 */
export function TierBadge({ confidenceScore, size = 'sm', showLabel = true }: TierBadgeProps) {
    const tier = getSignalTier(confidenceScore);

    const starSize = size === 'sm' ? 10 : 12;
    const textSize = size === 'sm' ? 'text-[10px]' : 'text-xs';

    return (
        <Badge
            variant="outline"
            className={`${tier.bgColor} ${tier.color} ${tier.borderColor} ${textSize} font-semibold gap-0.5`}
        >
            {Array.from({ length: tier.stars }).map((_, i) => (
                <Star key={i} size={starSize} weight="fill" />
            ))}
            {showLabel && <span className="ml-1">{tier.tier}</span>}
        </Badge>
    );
}

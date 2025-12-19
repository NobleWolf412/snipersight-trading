/**
 * Signal Tier Utilities
 * 
 * Quality tier classification for scan results.
 */

import type { ScanResult } from '@/utils/mockData';

export type SignalTier = 'TOP' | 'HIGH' | 'SOLID';

export interface TierInfo {
    tier: SignalTier;
    label: string;
    stars: number;
    color: string;
    bgColor: string;
    borderColor: string;
}

/**
 * Get quality tier based on confluence score
 */
export function getSignalTier(confidenceScore: number): TierInfo {
    if (confidenceScore >= 80) {
        return {
            tier: 'TOP',
            label: 'Top Tier',
            stars: 3,
            color: 'text-success',
            bgColor: 'bg-success/20',
            borderColor: 'border-success/50',
        };
    }
    if (confidenceScore >= 75) {
        return {
            tier: 'HIGH',
            label: 'High Quality',
            stars: 2,
            color: 'text-accent',
            bgColor: 'bg-accent/20',
            borderColor: 'border-accent/50',
        };
    }
    return {
        tier: 'SOLID',
        label: 'Solid',
        stars: 1,
        color: 'text-primary',
        bgColor: 'bg-primary/20',
        borderColor: 'border-primary/50',
    };
}

/**
 * Calculate aggregate statistics for scan results
 */
export function calculateScanStats(results: ScanResult[], rejections: any, metadata: any) {
    const total = results.length;
    const rejected = rejections?.total_rejected || 0;
    const scanned = metadata?.scanned || total + rejected;
    const passRate = scanned > 0 ? (total / scanned) * 100 : 0;

    // Confidence distribution
    const avgConfidence = total > 0
        ? results.reduce((sum, r) => sum + (r.confidenceScore || 0), 0) / total
        : 0;

    // Tier distribution
    const tierCounts = { TOP: 0, HIGH: 0, SOLID: 0 };
    results.forEach(r => {
        const tier = getSignalTier(r.confidenceScore || 0);
        tierCounts[tier.tier]++;
    });

    // Direction bias
    const longCount = results.filter(r => r.trendBias === 'BULLISH').length;
    const shortCount = results.filter(r => r.trendBias === 'BEARISH').length;
    const biasRatio = total > 0 ? Math.max(longCount, shortCount) / total : 0;
    const dominantBias = longCount > shortCount ? 'LONG' : shortCount > longCount ? 'SHORT' : 'NEUTRAL';

    // EV calculation
    const avgEV = total > 0
        ? results.reduce((sum, r) => {
            const rr = (r as any)?.riskReward ?? 1.5;
            const p = Math.max(0.2, Math.min(0.85, (r.confidenceScore || 50) / 100));
            return sum + (p * rr - (1 - p));
        }, 0) / total
        : 0;

    // Quality grade
    let qualityGrade: 'A+' | 'A' | 'B+' | 'B' | 'C';
    if (avgConfidence >= 80 && passRate >= 50) qualityGrade = 'A+';
    else if (avgConfidence >= 75) qualityGrade = 'A';
    else if (avgConfidence >= 70) qualityGrade = 'B+';
    else if (avgConfidence >= 65) qualityGrade = 'B';
    else qualityGrade = 'C';

    return {
        total,
        rejected,
        scanned,
        passRate,
        avgConfidence,
        tierCounts,
        longCount,
        shortCount,
        biasRatio,
        dominantBias,
        avgEV,
        qualityGrade,
    };
}

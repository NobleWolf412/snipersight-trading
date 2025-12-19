import { useState, useMemo, useEffect, useRef } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Funnel, SortAscending, SortDescending, Download, Copy, Check,
    CaretDown, X, Warning, Clock, CurrencyCircleDollar
} from '@phosphor-icons/react';
import { getSignalTier } from '@/utils/signalTiers';
import type { ScanResult } from '@/utils/mockData';

export type SortField = 'confidence' | 'ev' | 'pair' | 'riskReward';
export type SortDirection = 'asc' | 'desc';
export type TierFilter = 'all' | 'TOP' | 'HIGH' | 'SOLID';
export type BiasFilter = 'all' | 'BULLISH' | 'BEARISH';

interface TableControlsProps {
    results: ScanResult[];
    onFilteredResults: (results: ScanResult[]) => void;
    onSortChange: (field: SortField, direction: SortDirection) => void;
}

interface FilterState {
    tier: TierFilter;
    bias: BiasFilter;
    minConfidence: number;
}

// EV calculation helper (moved outside component to avoid recreation)
function getEV(r: ScanResult): number {
    const metaEV = (r as any)?.metadata?.ev?.expected_value;
    if (typeof metaEV === 'number') return metaEV;
    const rr = (r as any)?.riskReward ?? 1.5;
    const pRaw = (r.confidenceScore ?? 50) / 100;
    const p = Math.max(0.2, Math.min(0.85, pRaw));
    return p * rr - (1 - p) * 1.0;
}

/**
 * TableControls - Filter, sort, and export controls for the results table
 */
export function TableControls({ results, onFilteredResults, onSortChange }: TableControlsProps) {
    const [filters, setFilters] = useState<FilterState>({
        tier: 'all',
        bias: 'all',
        minConfidence: 0,
    });
    const [sortField, setSortField] = useState<SortField>('confidence');
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
    const [showFilters, setShowFilters] = useState(false);
    const [copied, setCopied] = useState(false);

    // Apply filters and sorting
    const filteredResults = useMemo(() => {
        let filtered = [...results];

        // Tier filter
        if (filters.tier !== 'all') {
            filtered = filtered.filter(r => getSignalTier(r.confidenceScore).tier === filters.tier);
        }

        // Bias filter
        if (filters.bias !== 'all') {
            filtered = filtered.filter(r => r.trendBias === filters.bias);
        }

        // Min confidence filter
        if (filters.minConfidence > 0) {
            filtered = filtered.filter(r => r.confidenceScore >= filters.minConfidence);
        }

        // Sort
        filtered.sort((a, b) => {
            let aVal: number | string = 0;
            let bVal: number | string = 0;

            switch (sortField) {
                case 'confidence':
                    aVal = a.confidenceScore;
                    bVal = b.confidenceScore;
                    break;
                case 'ev':
                    aVal = getEV(a);
                    bVal = getEV(b);
                    break;
                case 'pair':
                    aVal = a.pair;
                    bVal = b.pair;
                    break;
                case 'riskReward':
                    aVal = (a as any).riskReward || 0;
                    bVal = (b as any).riskReward || 0;
                    break;
            }

            if (typeof aVal === 'string') {
                return sortDirection === 'asc'
                    ? aVal.localeCompare(bVal as string)
                    : (bVal as string).localeCompare(aVal);
            }
            return sortDirection === 'asc' ? aVal - (bVal as number) : (bVal as number) - aVal;
        });

        return filtered;
    }, [results, filters, sortField, sortDirection]);

    // Notify parent of filtered results changes (in useEffect, not during render!)
    // Using a ref to store the callback to avoid dependency issues
    const onFilteredResultsRef = useRef(onFilteredResults);
    onFilteredResultsRef.current = onFilteredResults;

    useEffect(() => {
        onFilteredResultsRef.current(filteredResults);
    }, [filteredResults]);

    const handleSort = (field: SortField) => {
        if (field === sortField) {
            const newDir = sortDirection === 'asc' ? 'desc' : 'asc';
            setSortDirection(newDir);
            onSortChange(field, newDir);
        } else {
            setSortField(field);
            setSortDirection('desc');
            onSortChange(field, 'desc');
        }
    };

    const handleExportCSV = () => {
        const headers = ['Pair', 'Tier', 'Confidence', 'EV', 'Bias', 'R:R', 'Entry Type'];
        const rows = filteredResults.map(r => [
            r.pair,
            getSignalTier(r.confidenceScore).tier,
            r.confidenceScore.toFixed(1),
            getEV(r).toFixed(2),
            r.trendBias,
            ((r as any).riskReward || 0).toFixed(1),
            (r as any).plan_type || 'N/A'
        ]);

        const csv = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `scan-results-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleCopyToClipboard = async () => {
        const text = filteredResults
            .map(r => `${r.pair}: ${r.confidenceScore.toFixed(1)}% (${r.trendBias})`)
            .join('\n');

        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const clearFilters = () => {
        setFilters({ tier: 'all', bias: 'all', minConfidence: 0 });
    };

    const hasActiveFilters = filters.tier !== 'all' || filters.bias !== 'all' || filters.minConfidence > 0;
    const tierCounts = {
        TOP: results.filter(r => getSignalTier(r.confidenceScore).tier === 'TOP').length,
        HIGH: results.filter(r => getSignalTier(r.confidenceScore).tier === 'HIGH').length,
        SOLID: results.filter(r => getSignalTier(r.confidenceScore).tier === 'SOLID').length,
    };

    return (
        <div className="space-y-3">
            {/* Main Controls Row */}
            <div className="flex flex-wrap items-center gap-2 justify-between">
                {/* Filter Toggle */}
                <div className="flex items-center gap-2">
                    <Button
                        variant={showFilters ? "default" : "outline"}
                        size="sm"
                        onClick={() => setShowFilters(!showFilters)}
                        className={`gap-1.5 ${showFilters ? 'bg-accent text-accent-foreground' : ''}`}
                    >
                        <Funnel size={16} weight={showFilters ? "fill" : "regular"} />
                        Filters
                        {hasActiveFilters && (
                            <Badge className="ml-1 bg-primary/20 text-primary text-[10px] px-1.5">
                                {filteredResults.length}/{results.length}
                            </Badge>
                        )}
                    </Button>

                    {/* Quick Tier Buttons */}
                    <div className="hidden sm:flex items-center gap-1">
                        {(['all', 'TOP', 'HIGH', 'SOLID'] as TierFilter[]).map(tier => (
                            <Button
                                key={tier}
                                variant={filters.tier === tier ? "default" : "ghost"}
                                size="sm"
                                onClick={() => setFilters(f => ({ ...f, tier }))}
                                className={`text-xs h-7 px-2 ${filters.tier === tier
                                    ? tier === 'TOP' ? 'bg-success/20 text-success hover:bg-success/30'
                                        : tier === 'HIGH' ? 'bg-accent/20 text-accent hover:bg-accent/30'
                                            : tier === 'SOLID' ? 'bg-primary/20 text-primary hover:bg-primary/30'
                                                : 'bg-muted'
                                    : ''
                                    }`}
                            >
                                {tier === 'all' ? 'All' : `${tier} (${tierCounts[tier]})`}
                            </Button>
                        ))}
                    </div>

                    {hasActiveFilters && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={clearFilters}
                            className="text-xs h-7 text-muted-foreground hover:text-foreground"
                        >
                            <X size={14} />
                            Clear
                        </Button>
                    )}
                </div>

                {/* Sort & Export */}
                <div className="flex items-center gap-2">
                    {/* Sort Dropdown */}
                    <div className="flex items-center gap-1 bg-background/60 rounded-lg border border-border/50 p-1">
                        <span className="text-xs text-muted-foreground px-2 hidden sm:inline">Sort:</span>
                        {(['confidence', 'ev', 'riskReward', 'pair'] as SortField[]).map(field => (
                            <Button
                                key={field}
                                variant={sortField === field ? "secondary" : "ghost"}
                                size="sm"
                                onClick={() => handleSort(field)}
                                className="text-xs h-7 px-2 gap-1"
                            >
                                {field === 'confidence' ? 'Conf' : field === 'riskReward' ? 'R:R' : field.toUpperCase()}
                                {sortField === field && (
                                    sortDirection === 'desc'
                                        ? <SortDescending size={12} />
                                        : <SortAscending size={12} />
                                )}
                            </Button>
                        ))}
                    </div>

                    {/* Export Buttons */}
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleExportCSV}
                        className="gap-1.5 text-xs h-8"
                    >
                        <Download size={14} />
                        <span className="hidden sm:inline">CSV</span>
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopyToClipboard}
                        className="gap-1.5 text-xs h-8"
                    >
                        {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                        <span className="hidden sm:inline">{copied ? 'Copied!' : 'Copy'}</span>
                    </Button>
                </div>
            </div>

            {/* Expanded Filters Panel */}
            {showFilters && (
                <div className="p-4 bg-background/60 rounded-lg border border-border/50 animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        {/* Tier Filter */}
                        <div>
                            <label className="text-xs text-muted-foreground uppercase tracking-wide mb-2 block">
                                Quality Tier
                            </label>
                            <div className="flex flex-wrap gap-1">
                                {(['all', 'TOP', 'HIGH', 'SOLID'] as TierFilter[]).map(tier => (
                                    <Badge
                                        key={tier}
                                        variant={filters.tier === tier ? "default" : "outline"}
                                        className={`cursor-pointer transition-colors ${filters.tier === tier
                                            ? tier === 'TOP' ? 'bg-success text-success-foreground'
                                                : tier === 'HIGH' ? 'bg-accent text-accent-foreground'
                                                    : tier === 'SOLID' ? 'bg-primary text-primary-foreground'
                                                        : ''
                                            : 'hover:bg-muted'
                                            }`}
                                        onClick={() => setFilters(f => ({ ...f, tier }))}
                                    >
                                        {tier === 'all' ? 'All Tiers' : tier}
                                    </Badge>
                                ))}
                            </div>
                        </div>

                        {/* Bias Filter */}
                        <div>
                            <label className="text-xs text-muted-foreground uppercase tracking-wide mb-2 block">
                                Direction
                            </label>
                            <div className="flex flex-wrap gap-1">
                                {(['all', 'BULLISH', 'BEARISH'] as BiasFilter[]).map(bias => (
                                    <Badge
                                        key={bias}
                                        variant={filters.bias === bias ? "default" : "outline"}
                                        className={`cursor-pointer transition-colors ${filters.bias === bias
                                            ? bias === 'BULLISH' ? 'bg-success text-success-foreground'
                                                : bias === 'BEARISH' ? 'bg-destructive text-destructive-foreground'
                                                    : ''
                                            : 'hover:bg-muted'
                                            }`}
                                        onClick={() => setFilters(f => ({ ...f, bias }))}
                                    >
                                        {bias === 'all' ? 'All' : bias}
                                    </Badge>
                                ))}
                            </div>
                        </div>

                        {/* Min Confidence */}
                        <div>
                            <label className="text-xs text-muted-foreground uppercase tracking-wide mb-2 block">
                                Min Confidence
                            </label>
                            <div className="flex flex-wrap gap-1">
                                {[0, 70, 75, 80].map(val => (
                                    <Badge
                                        key={val}
                                        variant={filters.minConfidence === val ? "default" : "outline"}
                                        className="cursor-pointer hover:bg-muted transition-colors"
                                        onClick={() => setFilters(f => ({ ...f, minConfidence: val }))}
                                    >
                                        {val === 0 ? 'Any' : `≥${val}%`}
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Results Count */}
            {hasActiveFilters && (
                <div className="text-xs text-muted-foreground">
                    Showing {filteredResults.length} of {results.length} signals
                    {filters.tier !== 'all' && ` • ${filters.tier} tier only`}
                    {filters.bias !== 'all' && ` • ${filters.bias} only`}
                    {filters.minConfidence > 0 && ` • ≥${filters.minConfidence}% confidence`}
                </div>
            )}
        </div>
    );
}

/**
 * RiskAlertBadge - Shows risk indicators for individual signals
 */
interface RiskAlertBadgeProps {
    result: ScanResult;
}

export function RiskAlertBadge({ result }: RiskAlertBadgeProps) {
    const alerts: { type: 'warning' | 'info'; label: string; icon: React.ReactNode }[] = [];

    // ATR fallback entry (less precise)
    if ((result as any).plan_type === 'ATR_FALLBACK') {
        alerts.push({
            type: 'warning',
            label: 'ATR Entry',
            icon: <Warning size={10} />
        });
    }

    // Borderline confidence
    if (result.confidenceScore < 75 && result.confidenceScore >= 65) {
        alerts.push({
            type: 'info',
            label: 'Borderline',
            icon: <Clock size={10} />
        });
    }

    // Very low R:R
    const rr = (result as any).riskReward;
    if (rr && rr < 1.8) {
        alerts.push({
            type: 'info',
            label: 'Low R:R',
            icon: <CurrencyCircleDollar size={10} />
        });
    }

    // Reversal trade
    if ((result as any).reversal_context?.is_reversal) {
        alerts.push({
            type: 'warning',
            label: 'Reversal',
            icon: <Warning size={10} />
        });
    }

    if (alerts.length === 0) {
        return (
            <Badge variant="outline" className="text-[10px] text-success border-success/30 bg-success/10">
                ✓ Clean
            </Badge>
        );
    }

    return (
        <div className="flex flex-wrap gap-1">
            {alerts.slice(0, 2).map((alert, i) => (
                <Badge
                    key={i}
                    variant="outline"
                    className={`text-[10px] gap-0.5 ${alert.type === 'warning'
                        ? 'text-warning border-warning/30 bg-warning/10'
                        : 'text-muted-foreground border-border bg-muted/50'
                        }`}
                >
                    {alert.icon}
                    {alert.label}
                </Badge>
            ))}
            {alerts.length > 2 && (
                <Badge variant="outline" className="text-[10px] text-muted-foreground">
                    +{alerts.length - 2}
                </Badge>
            )}
        </div>
    );
}

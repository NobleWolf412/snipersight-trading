import { createContext, useContext, ReactNode, useEffect, useState, useCallback } from 'react';
import { api } from '@/utils/api';
import { useLocalStorage } from '@/hooks/useLocalStorage';

// Types adapted from components
export interface CycleData {
    symbol: string;
    dcl: {
        days_since: number | null;
        confirmation: string;
        expected_window: { min_days: number; max_days: number };
    } | null;
    wcl: {
        days_since: number | null;
        confirmation: string;
        expected_window: { min_days: number; max_days: number };
    } | null;
    phase: 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN' | 'UNKNOWN';
    translation: 'LEFT_TRANSLATED' | 'MID_TRANSLATED' | 'RIGHT_TRANSLATED' | 'UNKNOWN';
    trade_bias: 'LONG' | 'SHORT' | 'NEUTRAL';
    stochastic_rsi: {
        k: number | null;
        d: number | null;
        zone: 'oversold' | 'overbought' | 'neutral';
    };
    temporal?: {
        score: number;
        is_active_window: boolean;
        day_of_week: string;
    };
    timestamp: string;
}

export interface HTFOpportunity {
    symbol: string;
    level: {
        price: number;
        level_type: string;
        timeframe: string;
        strength: number;
        touches: number;
        proximity_pct: number;
    };
    current_price: number;
    recommended_mode: string;
    rationale: string;
    confluence_factors: string[];
    expected_move_pct: number;
    confidence: number;
}

export interface HTFOpportunitiesData {
    opportunities: HTFOpportunity[];
    total: number;
    timestamp: string;
}

export interface RegimeData {
    composite: string;
    score: number;
    dimensions: {
        trend: string;
        volatility: string;
        liquidity: string;
        risk_appetite: string;
        derivatives: string;
    };
    trend_score: number;
    volatility_score: number;
    liquidity_score: number;
    risk_score: number;
    derivatives_score: number;
    dominance?: {
        btc_d: number;
        alt_d: number;
        stable_d: number;
    };
    timestamp: string;
}

interface LandingContextType {
    cycles: CycleData | null;
    htf: HTFOpportunitiesData | null;
    regime: RegimeData | null;
    isLoading: boolean;
    progress: number;
    error: string | null;
    refreshData: () => Promise<void>;
}

const LandingContext = createContext<LandingContextType | undefined>(undefined);

export function LandingProvider({ children }: { children: ReactNode }) {
    // Use localStorage for caching to enable instant load
    // Note: useLocalStorage returns [value, setValue]
    const [cycles, setCycles] = useLocalStorage<CycleData | null>('landing_cycles', null);
    const [htf, setHtf] = useLocalStorage<HTFOpportunitiesData | null>('landing_htf', null);
    const [regime, setRegime] = useLocalStorage<RegimeData | null>('landing_regime', null);

    // Initial loading state relies on whether we have cached data
    const [isLoading, setIsLoading] = useState<boolean>(() => {
        // If we have data in localStorage (initialized above), we are not loading
        return !cycles && !htf && !regime;
    });

    const [progress, setProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);

    const refreshData = useCallback(async () => {
        // Only show progress/loading logic if we are actually in a loading state (no cache)
        const hasCache = !!(cycles || htf || regime);
        let progressInterval: NodeJS.Timeout | null = null;

        if (!hasCache) {
            setProgress(5);
            // Simulate realistic network progress curve
            progressInterval = setInterval(() => {
                setProgress(prev => {
                    // Stop if complete or barely moving
                    if (prev >= 90) return prev;

                    // Stage 1: Fast initial connection (0-30%)
                    if (prev < 30) return prev + Math.random() * 5 + 2;

                    // Stage 2: Handshaking (30-60%)
                    if (prev < 60) return prev + Math.random() * 2 + 1;

                    // Stage 3: Data transfer (60-80%)
                    if (prev < 80) return prev + Math.random() * 1;

                    // Stage 4: Processing (80-99%) - Very slow crawl
                    if (prev < 99) return prev + 0.2;

                    return prev;
                });
            }, 200);
        } else {
            // If we have cache, we might want to set progress to 100 instantly so components reading it are happy
            setProgress(100);
        }

        try {
            // Parallel fetch for speed
            const [cyclesRes, htfRes, regimeRes] = await Promise.all([
                api.getMarketCycles('BTCUSDT'),
                api.getHTFOpportunities({ min_confidence: 60 }),
                api.getMarketRegime()
            ]);

            if (progressInterval) {
                clearInterval(progressInterval);
                setProgress(100);
            }

            // Process results independently to handle partial failures gracefully
            if (cyclesRes.data) setCycles(cyclesRes.data);
            if (htfRes.data) setHtf(htfRes.data);
            if (regimeRes.data) setRegime(regimeRes.data);

            if (cyclesRes.error && htfRes.error && regimeRes.error) {
                // Only error if we have NO data at all
                if (!hasCache) {
                    setError("System Offline: Unable to fetch market intelligence.");
                }
            } else {
                setError(null);
            }

        } catch (err) {
            console.error("[LandingContext] Load failed:", err);
            if (progressInterval) clearInterval(progressInterval);
            if (!hasCache) {
                setError("Network error: Failed to connect to intelligence grid.");
            }
        } finally {
            if (!hasCache) {
                // Small delay to let the user see 100% on initial load
                setTimeout(() => {
                    setIsLoading(false);
                }, 500);
            } else {
                // Ensure loading is false
                setIsLoading(false);
            }
        }
    }, [cycles, htf, regime, setCycles, setHtf, setRegime]);

    // Initial load
    useEffect(() => {
        refreshData();
        // Auto-refresh every 60s
        const id = setInterval(() => {
            // Silent refresh - do not trigger loading screen or progress bar updates (managed by refreshData condition)
            // Actually refreshData checks !hasCache, but hasCache is boolean from closure?
            // No, refreshData has deps [cycles, ...], so it updates.
            // But we don't want to re-trigger the interval.
            // Let's just call the APIs directly to be safe and avoid side effects.
            api.getMarketCycles('BTCUSDT').then(res => res.data && setCycles(res.data));
            api.getHTFOpportunities({ min_confidence: 60 }).then(res => res.data && setHtf(res.data));
            api.getMarketRegime().then(res => res.data && setRegime(res.data));
        }, 60000);
        return () => clearInterval(id);
    }, [refreshData, setCycles, setHtf, setRegime]);

    return (
        <LandingContext.Provider value={{ cycles, htf, regime, isLoading, progress, error, refreshData }}>
            {children}
        </LandingContext.Provider>
    );
}

export function useLandingData() {
    const context = useContext(LandingContext);
    if (context === undefined) {
        throw new Error('useLandingData must be used within a LandingProvider');
    }
    return context;
}

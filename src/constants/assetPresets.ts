/**
 * Asset Category Presets
 * 
 * Pre-configured asset combinations for common trading styles.
 */

export interface AssetPreset {
    id: string;
    name: string;
    description: string;
    icon: string;
    categories: {
        majors: boolean;
        altcoins: boolean;
        memeMode: boolean;
    };
    expectedSignals: string;
    volatility: 'Low' | 'Medium' | 'High';
    riskLevel: 'Conservative' | 'Balanced' | 'Aggressive';
    recommended: boolean;
}

export const ASSET_PRESETS: AssetPreset[] = [
    {
        id: 'conservative',
        name: 'Blue Chips Only',
        description: 'BTC, ETH, SOL - Most stable, tighter spreads',
        icon: '🛡️',
        categories: { majors: true, altcoins: false, memeMode: false },
        expectedSignals: '2-5/scan',
        volatility: 'Low',
        riskLevel: 'Conservative',
        recommended: false,
    },
    {
        id: 'balanced',
        name: 'Balanced',
        description: 'Majors + top alts - Good signal volume',
        icon: '⚖️',
        categories: { majors: true, altcoins: true, memeMode: false },
        expectedSignals: '8-15/scan',
        volatility: 'Medium',
        riskLevel: 'Balanced',
        recommended: true,
    },
    {
        id: 'aggressive',
        name: 'All Markets',
        description: 'Everything including meme coins',
        icon: '🚀',
        categories: { majors: true, altcoins: true, memeMode: true },
        expectedSignals: '20+/scan',
        volatility: 'High',
        riskLevel: 'Aggressive',
        recommended: false,
    },
];

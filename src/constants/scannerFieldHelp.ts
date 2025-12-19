/**
 * Scanner Configuration Field Help
 * 
 * Contextual tooltips and guidance for all scanner configuration fields.
 */

export interface FieldHelp {
    label: string;
    tooltip: string;
    example?: string;
    warning?: string;
    learnMore?: string;
}

export const SCANNER_FIELD_HELP: Record<string, FieldHelp> = {
    exchange: {
        label: 'Exchange',
        tooltip: 'Select your trading venue. Different exchanges have varying liquidity, fees, and geographic availability.',
        example: 'Phemex: Fast execution, no geo-blocking for US traders',
        warning: 'Ensure your account is funded and API keys configured before scanning',
    },
    leverage: {
        label: 'Leverage',
        tooltip: 'Position sizing multiplier. 1x = spot trading, 10x = 10:1 leverage. Higher leverage amplifies both gains AND losses.',
        example: '1x: $100 → $100 position | 10x: $100 → $1000 position',
        warning: '⚠️ High leverage (>10x) requires tight stops. Recommended: 1-5x for beginners',
    },
    topPairs: {
        label: 'Pairs to Scan',
        tooltip: 'Number of trading pairs to analyze. More pairs = more signals but longer scan time. Pairs are ranked by volume and liquidity.',
        example: '20 pairs ≈ 30-60 seconds | 50 pairs ≈ 1-2 minutes',
    },
    majors: {
        label: 'Majors',
        tooltip: 'Top cryptocurrencies by market cap (BTC, ETH, SOL, BNB, XRP, etc). Most stable with highest liquidity.',
        example: 'Best for: Lower volatility, cleaner signals, tighter spreads',
    },
    altcoins: {
        label: 'Altcoins',
        tooltip: 'Mid-cap coins outside the top 10 (LINK, AVAX, DOT, NEAR, etc). More volatile with higher potential moves.',
        example: 'Best for: Bigger swings, more trading opportunities',
    },
    memeMode: {
        label: 'Meme Mode',
        tooltip: 'Include high-volatility meme/small-cap coins (DOGE, SHIB, PEPE, etc). Highest risk with potential for extreme moves.',
        warning: '⚠️ Meme coins can have 10%+ swings in minutes. Use small position sizes!',
    },
    macroOverlay: {
        label: 'Macro Overlay',
        tooltip: 'Enable BTC/ALT dominance flow analysis. Bias signals based on which asset class is absorbing capital.',
        example: 'BTC dominance rising → favor BTC longs | ALT season → favor altcoin longs',
    },
};

export const LEVERAGE_WARNING_THRESHOLDS = {
    beginner: 5,    // Warn above 5x
    moderate: 20,   // Strong warning above 20x
    extreme: 50,    // Critical warning above 50x
};

export function getLeverageWarning(leverage: number): { severity: 'none' | 'info' | 'warning' | 'danger'; message: string } | null {
    if (leverage <= LEVERAGE_WARNING_THRESHOLDS.beginner) {
        return null;
    }
    if (leverage <= LEVERAGE_WARNING_THRESHOLDS.moderate) {
        return {
            severity: 'info',
            message: `${leverage}x leverage requires disciplined stop-loss management`,
        };
    }
    if (leverage <= LEVERAGE_WARNING_THRESHOLDS.extreme) {
        return {
            severity: 'warning',
            message: `⚠️ ${leverage}x is high leverage - liquidation risk increases significantly`,
        };
    }
    return {
        severity: 'danger',
        message: `🚨 ${leverage}x is extreme leverage - for experienced traders only`,
    };
}

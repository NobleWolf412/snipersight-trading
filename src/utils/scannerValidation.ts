/**
 * Scanner Validation
 * 
 * Pre-scan validation logic to catch configuration issues before arming.
 */

import type { ScanConfig } from '@/context/ScannerContext';
import type { ScannerMode } from '@/utils/api';

export interface ValidationIssue {
    id: string;
    severity: 'error' | 'warning' | 'info';
    message: string;
    suggestion?: string;
    autoFix?: {
        label: string;
        apply: (config: ScanConfig) => Partial<ScanConfig>;
    };
}

/**
 * Validate scanner configuration before arming
 */
export function validateScannerConfig(
    config: ScanConfig,
    selectedMode: ScannerMode | null
): ValidationIssue[] {
    const issues: ValidationIssue[] = [];

    // 1. Check asset selection - at least one category must be enabled
    if (!config.categories.majors && !config.categories.altcoins && !config.categories.memeMode) {
        issues.push({
            id: 'no-assets',
            severity: 'error',
            message: 'No asset categories selected',
            suggestion: 'Enable at least Majors or Altcoins to scan',
            autoFix: {
                label: 'Enable Majors & Altcoins',
                apply: (c) => ({
                    categories: { ...c.categories, majors: true, altcoins: true },
                }),
            },
        });
    }

    // 2. Meme mode without other categories warning
    if (config.categories.memeMode && !config.categories.majors && !config.categories.altcoins) {
        issues.push({
            id: 'meme-only',
            severity: 'warning',
            message: 'Only meme coins selected - high volatility signals only',
            suggestion: 'Consider enabling Majors for more stable signals',
        });
    }

    // 3. High leverage warning
    if (config.leverage >= 20) {
        issues.push({
            id: 'high-leverage',
            severity: 'warning',
            message: `${config.leverage}x leverage is high risk`,
            suggestion: 'Consider 5-10x for most trading styles',
        });
    }

    if (config.leverage >= 50) {
        issues.push({
            id: 'extreme-leverage',
            severity: 'error',
            message: `${config.leverage}x leverage - extreme liquidation risk`,
            suggestion: 'Only use with tight stops and small position sizes',
        });
    }

    // 4. Low pair count with meme mode
    if (config.topPairs < 10 && config.categories.memeMode) {
        issues.push({
            id: 'low-pairs-meme',
            severity: 'info',
            message: 'Low pair count may miss meme coin opportunities',
            suggestion: 'Increase to 30+ for better meme coverage',
        });
    }

    // 5. Selected mode validation
    if (!selectedMode) {
        issues.push({
            id: 'no-mode',
            severity: 'error',
            message: 'No scanner mode selected',
            suggestion: 'Select a mode from the profile cards above',
        });
    }

    // 6. Overwatch mode with low pair count
    if (selectedMode?.name === 'overwatch' && config.topPairs < 20) {
        issues.push({
            id: 'overwatch-low-pairs',
            severity: 'info',
            message: 'Overwatch mode works best with more pairs',
            suggestion: 'Increase to 30+ for better A+ setup discovery',
        });
    }

    // 7. Strike mode warning
    if (selectedMode?.name === 'strike') {
        issues.push({
            id: 'strike-mode-info',
            severity: 'info',
            message: 'Strike mode generates more signals with lower confluence',
            suggestion: 'Expect higher volume but lower quality signals',
        });
    }

    return issues;
}

/**
 * Check if validation has blocking errors
 */
export function hasBlockingErrors(issues: ValidationIssue[]): boolean {
    return issues.some(issue => issue.severity === 'error');
}

/**
 * Get severity color class
 */
export function getSeverityColor(severity: ValidationIssue['severity']): string {
    switch (severity) {
        case 'error':
            return 'text-destructive border-destructive/50 bg-destructive/10';
        case 'warning':
            return 'text-warning border-warning/50 bg-warning/10';
        case 'info':
            return 'text-primary border-primary/50 bg-primary/10';
        default:
            return 'text-muted-foreground';
    }
}

/**
 * Get severity icon
 */
export function getSeverityIcon(severity: ValidationIssue['severity']): string {
    switch (severity) {
        case 'error':
            return '❌';
        case 'warning':
            return '⚠️';
        case 'info':
            return 'ℹ️';
        default:
            return '';
    }
}

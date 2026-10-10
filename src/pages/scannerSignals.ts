import type { ScanHistoryEntry } from '@/services/scanHistoryService';
import { setupPlay, type Play } from '@/services/playInspector';
import { readDirection, readScore, validScore } from '@/utils/scoreEvidence';
// Categories contain only producer evidence; unavailable is selectable.
export const SETUPS = ['OB+FVG', 'BOS', 'CHoCH', 'LIQ-SWEEP', 'OB-RETEST', 'FVG-FILL', 'BREAKER', 'SMC', 'UNKNOWN'] as const;
export const TFS = ['1m', '5m', '15m', '1h', '4h', '1D', '1W', 'UNKNOWN'] as const;
export const REGIMES = ['TREND', 'RANGE', 'CHOP', 'UNKNOWN'] as const;
export type Setup = (typeof SETUPS)[number];
export type Tf = (typeof TFS)[number];
export type Regime = (typeof REGIMES)[number];
export type Direction = 'LONG' | 'SHORT';
export type TradeType = 'SWING' | 'INTRADAY' | 'SCALP';
export interface CardSignal {
    id: string;
    sym: string;
    dir: Direction;
    setup: Setup;
    score: number | undefined;
    scoreGate: number | undefined;
    scoreGatePassed?: boolean;
    evidenceEligible?: boolean;
    admissionPassed?: boolean;
    evidenceMissing?: string[];
    scoreModelVersion?: string;
    scorePolicyVersion?: string;
    tf: Tf;
    regime: Regime;
    mark: number;
    entry: number;
    sl: number;
    tp1: number;
    tp2: number;
    rr: number;
    age: number;
    rationale?: string;
    raw?: unknown;
    play: Play;
    // tradeType: backend-emitted scale classification (SWING/INTRADAY/SCALP).
    // Sourced from the scan-history result's `classification` (already produced
    // by convertSignalToScanResult), with `trade_type` and `setup_type` accepted
    // as backend-format fallbacks. Undefined when history predates the field
    // or the upstream pipeline didn't emit one.
    tradeType?: TradeType;
    // Convergence/conflict (plan §3d P1) — green sliver = synergy_bonus,
    // red sliver = conflict_penalty. Both pulled directly from the
    // scan-history `confluence_breakdown` (already passed through by
    // convertSignalToScanResult). Numbers, not percentages — the renderer
    // scales to a fixed visual range so a typical score's bonus/penalty
    // surface without burying lower-impact factors.
    synergyBonus?: number;
    conflictPenalty?: number;
}
// Normalize any of the backend-format trade-type aliases to the upper-case
// frontend enum. Returns undefined when the input is missing/unrecognized so
// the card can render a placeholder rather than a misleading chip.
function normalizeTradeType(raw: unknown): TradeType | undefined {
    if (typeof raw !== 'string')
        return undefined;
    const v = raw.trim().toUpperCase();
    if (v === 'SWING' || v === 'INTRADAY' || v === 'SCALP')
        return v;
    return undefined;
}
export function buildCardSignals(history: ScanHistoryEntry[]): CardSignal[] {
    const latest = history[0];
    if (!latest || !Array.isArray(latest.results) || latest.results.length === 0)
        return [];
    return latest.results.map((r: any, i: number): CardSignal | null => {
        const sym: string = r.pair ?? r.symbol ?? r.sym ?? 'UNKNOWN/USDT';
        const dir = readDirection(r);
        if (!dir)
            return null; // No directional evidence: do not invent a LONG.
        const category = <T extends string>(value: unknown, choices: readonly T[]): T => choices.find(choice => choice.toUpperCase() === String(value ?? '').toUpperCase()) ?? ('UNKNOWN' as T);
        const price = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : NaN;
        const entry: number = price(r.entryZone?.high ?? r.entry_near ?? r.entry ?? r.entry_price);
        const sl: number = price(r.stopLoss ?? r.stop_loss?.level ?? r.stop_loss ?? r.sl);
        const tp1: number = price(r.takeProfits?.[0] ?? r.targets?.[0]?.level ?? r.tp1);
        const tp2: number = price(r.takeProfits?.[1] ?? r.targets?.[1]?.level ?? r.tp2);
        const score = readScore(r);
        const scoreMetadata = r.confluence_breakdown?.metadata ?? r.metadata ?? {};
        const scoreGate = validScore(scoreMetadata.score_gate ?? latest.effectiveMinScore);
        const scoreGatePassed = scoreMetadata.score_gate_passed;
        const rr: number = price(r.riskReward ?? r.rr ?? r.risk_reward);
        const mark: number = Number(r.mark ?? r.mark_price ?? entry);
        const id: string = String(r.id ?? `card_${i}`);
        // Trade-type: prefer the convertSignalToScanResult-emitted `classification`
        // (already SWING/INTRADAY/SCALP). Fall back to raw backend fields for
        // history entries written by paths that bypass the converter.
        const tradeType = normalizeTradeType(r.classification ?? r.trade_type ?? r.setup_type);
        // Convergence/conflict — the breakdown object lives in two locations
        // depending on producer: top-level on raw backend signals, nested under
        // `confluence_breakdown` after convertSignalToScanResult. Read either.
        const cb = r.confluence_breakdown ?? r;
        const synergyBonus = typeof cb?.synergy_bonus === 'number' ? cb.synergy_bonus : undefined;
        const conflictPenalty = typeof cb?.conflict_penalty === 'number' ? cb.conflict_penalty : undefined;
        return {
            id,
            sym,
            dir,
            setup: category(r.setup_pattern ?? r.plan_type, SETUPS),
            score,
            scoreGate,
            scoreGatePassed: typeof scoreGatePassed === 'boolean' ? scoreGatePassed : undefined,
            evidenceEligible: typeof scoreMetadata.evidence_eligible === 'boolean' ? scoreMetadata.evidence_eligible : undefined,
            admissionPassed: typeof scoreMetadata.admission_passed === 'boolean' ? scoreMetadata.admission_passed : undefined,
            evidenceMissing: Array.isArray(scoreMetadata.evidence_missing)
                ? scoreMetadata.evidence_missing.filter((reason: unknown): reason is string => typeof reason === 'string') : undefined,
            scoreModelVersion: typeof scoreMetadata.score_model_version === 'string' ? scoreMetadata.score_model_version : undefined,
            scorePolicyVersion: typeof scoreMetadata.score_policy_version === 'string' ? scoreMetadata.score_policy_version : undefined,
            tf: category(r.timeframe, TFS),
            regime: category(r.regime?.symbol_regime?.trend === 'up' || r.regime?.symbol_regime?.trend === 'down' ? 'TREND' : r.regime?.symbol_regime?.trend === 'sideways' ? 'RANGE' : r.regime_label, REGIMES),
            mark,
            entry,
            sl,
            tp1,
            tp2,
            rr,
            age: Math.max(0, Math.floor((Date.now() - Date.parse(r.timestamp || latest.timestamp)) / 60000)),
            rationale: r.rationale, raw: r,
            play: setupPlay(r, latest, { score, threshold: scoreGate, tradeType }),
            tradeType,
            synergyBonus,
            conflictPenalty,
        };
    }).filter((signal): signal is CardSignal => signal !== null);
}
// ─── Main ────────────────────────────────────────────────────────────────

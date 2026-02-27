export interface ConfluenceFactor {
    name: string;
    score: number;
    weight: number;
    rationale: string;
    weighted_score: number;
}

export interface ConfluenceBreakdown {
    total_score: number;
    synergy_bonus: number;
    conflict_penalty: number;
    regime: string;
    htf_aligned: boolean;
    btc_impulse_gate: boolean;
    factors: ConfluenceFactor[];
}

/** A confluence score is a heuristic on 0–100, not a win probability. */
export function validScore(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100
    ? value : undefined;
}

export function readScore(result: any): number | undefined {
  return validScore(result.confidenceScore ?? result.score ?? result.confidence_score
    ?? result.confluence_score ?? result.confluence_breakdown?.total_score ?? result.confluence);
}

export function readDirection(result: any): 'LONG' | 'SHORT' | undefined {
  const raw = String(result.trendBias ?? result.direction ?? result.side ?? result.dir ?? '').toUpperCase();
  if (['LONG', 'BULLISH', 'BUY'].includes(raw)) return 'LONG';
  if (['SHORT', 'BEARISH', 'SELL'].includes(raw)) return 'SHORT';
  return undefined;
}

export function passesScoreGate(score: number | undefined, gate: number | undefined, recorded?: boolean): boolean {
  if (score === undefined) return false;
  if (typeof recorded === 'boolean') return recorded;
  if (gate === undefined) return false;
  // Historical fallback: compare at the scanner's one-decimal precision.
  // Exact binary quarter ties need half-to-even (Python round), not JS half-up.
  const rounded = (value: number) => {
    const scaled = value * 10;
    const lower = Math.floor(scaled);
    if (Number.isInteger(value * 4) && scaled - lower === 0.5) {
      return (lower % 2 === 0 ? lower : lower + 1) / 10;
    }
    return Number(value.toFixed(1));
  };
  return rounded(score) >= rounded(gate);
}

export function formatScore(score: number | undefined): string {
  return score === undefined ? '—' : score.toFixed(1);
}

export interface AdmissionEvidence {
  score: number | undefined;
  scoreGate: number | undefined;
  scoreGatePassed?: boolean;
  evidenceEligible?: boolean;
  admissionPassed?: boolean;
  scoreModelVersion?: string;
}

/** Evidence requirements and the numeric cutoff are separate recorded decisions. */
export function passesAdmission(evidence: AdmissionEvidence): boolean {
  if (validScore(evidence.score) === undefined || evidence.evidenceEligible === false
      || evidence.admissionPassed === false || evidence.scoreGatePassed === false) return false;
  if (evidence.scoreModelVersion === 'family-evidence-v2' && evidence.evidenceEligible !== true) return false;
  if (evidence.admissionPassed === true) return true;
  return passesScoreGate(evidence.score, evidence.scoreGate, evidence.scoreGatePassed);
}

export function admissionLabel(evidence: AdmissionEvidence): string {
  if (evidence.evidenceEligible === false) return 'EVIDENCE REQUIREMENTS NOT MET';
  if (evidence.scoreModelVersion === 'family-evidence-v2' && evidence.evidenceEligible !== true) {
    return 'REQUIRED EVIDENCE UNAVAILABLE';
  }
  if (evidence.scoreGatePassed === false) return 'BELOW SCORE GATE';
  if (evidence.admissionPassed === false) return 'ADMISSION NOT MET';
  if (validScore(evidence.score) === undefined) return 'SCORE UNAVAILABLE';
  if (evidence.admissionPassed === true) return 'ADMISSION PASSED';
  if (passesScoreGate(evidence.score, evidence.scoreGate, evidence.scoreGatePassed)) {
    return evidence.evidenceEligible === true ? 'ADMISSION PASSED' : 'SCORE GATE PASSED';
  }
  return evidence.scoreGate === undefined && evidence.scoreGatePassed === undefined
    ? 'SCORE GATE UNAVAILABLE' : 'BELOW SCORE GATE';
}

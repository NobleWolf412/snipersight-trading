export type SourceTier = 'primary' | 'vendor' | 'supplementary';

export interface SourceRef {
  tier: SourceTier;
  title: string;
  url: string;
}

export interface ChapterMeta {
  id: string;
  num: number;
  title: string;
  color: string;
  summary: string;
  sourceRefs?: string[];
}

export type FixtureLens =
  | 'ob'
  | 'fvg'
  | 'bos'
  | 'sweep'
  | 'wyckoff'
  | 'regime'
  | 'killzone';

export interface FixtureBar {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export interface FixtureData {
  symbol: string;
  timeframe: string;
  source: string;
  window: { start: string; end: string; bar_count: number };
  bars: FixtureBar[];
}

export interface FixtureAnnotations {
  fixture: string;
  symbol: string;
  timeframe: string;
  window: { start: string; end: string; bar_count: number };
  narrative: string;
  ob: {
    bar_idx: number;
    timestamp: string;
    direction: 'bullish' | 'bearish';
    high: number;
    low: number;
    grade: string | null;
    displacement_strength: number;
    detection_method?: string;
    chapter_note: string;
  } | null;
  fvg: {
    bar_idx: number;
    timestamp: string;
    direction: 'bullish' | 'bearish';
    top: number;
    bottom: number;
    chapter_note: string;
  } | null;
  bos: {
    bar_idx: number;
    timestamp: string;
    direction: 'bullish' | 'bearish';
    break_level: number;
    broken_swing_idx: number;
    chapter_note: string;
  } | null;
  sweep: {
    bar_idx: number;
    timestamp: string;
    sweep_type: 'high' | 'low';
    level: number;
    confirmation_level: number | null;
    chapter_note: string;
  } | null;
  wyckoff_phase: { label: string; chapter_note: string } | null;
  regime_hint: { label: string; chapter_note: string } | null;
  kill_zone: { label: string | null; chapter_note: string } | null;
  score: number;
  lens_coverage: Record<FixtureLens, boolean>;
  notes: string;
}

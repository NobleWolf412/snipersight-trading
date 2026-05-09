// HUD chrome barrel — single import surface for the new design system.

// New HUD primitives (Phase 2c — port of prototype/shared.jsx)
export { Chip, type ChipKind } from './Chip';
export { Mini } from './Mini';
export { Modal } from './Modal';
export { PageHead } from './PageHead';
export { FooterStatus } from './FooterStatus';
export { Reticle } from './Reticle';
export { RiskBar } from './RiskBar';
export { SectionHead } from './SectionHead';
export { TacticalBgDom } from './TacticalBgDom';
export { Topbar } from './Topbar';
export { PhemexStatusPill } from './PhemexStatusPill';
export { ScannerModePicker } from './ScannerModePicker';
export { GauntletBreakdown, classifyStage, type GauntletStage } from './GauntletBreakdown';
export {
  applyTweaks,
  SHARED_TWEAK_DEFAULTS,
  type Tweaks,
  type AccentKey,
  type DensityKey,
} from './applyTweaks';
export {
  fmtMoney,
  fmtPct,
  fmtPrice,
  fmtDur,
  fmtNum,
} from './formatters';

// Legacy components (will be archived in Phase 6 once references are removed).
// Kept exported so existing pages still build during migration.
export { HudPanel } from './HudPanel';
export { TacticalCard } from './TacticalCard';
export { MissionBrief } from './MissionBrief';
export { TargetReticleOverlay } from './TargetReticleOverlay';

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
export {
  PhemexStatusPill,
  classifyPhemexHealth,
  type PhemexHealth,
  type PhemexSeverity,
  type PhemexClassifyResult,
} from './PhemexStatusPill';
export { ScannerModePicker } from './ScannerModePicker';
export { ActiveModeBadge } from './ActiveModeBadge';
export { GauntletBreakdown, classifyStage, type GauntletStage } from './GauntletBreakdown';
export { PipelineTracer } from './PipelineTracer';
export { ConfluenceBreakdown } from './ConfluenceBreakdown';
export { UniversePanel } from './UniversePanel';
export { DiagnoseWizard } from './DiagnoseWizard';
export { CycleHeartbeat } from './CycleHeartbeat';
export { MacroScoreTile } from './MacroScoreTile';
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

import { HudPanel } from './HudPanel';
import { TacticalCard } from './TacticalCard';
import { MissionBrief } from './MissionBrief';
import { TargetReticleOverlay } from './TargetReticleOverlay';
import { Crosshair, Lightning, Target } from '@phosphor-icons/react';

/**
 * Demo component showcasing all HUD components
 * Use this as a reference for implementing HUD UI in your pages
 */
export function HudComponentsDemo() {
  return (
    <div className="max-w-4xl mx-auto space-y-8 p-8">
      <h1 className="text-3xl font-bold text-primary">HUD Component Library</h1>
      
      {/* HudPanel Demo */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground">HudPanel</h2>
        <HudPanel 
          title="Control Center" 
          subtitle="Main tactical command interface"
          className="tactical-grid"
        >
          <p className="text-muted-foreground">
            Use HudPanel for main sections and control surfaces. 
            Add tactical-grid, scan-lines, or other HUD effects via className.
          </p>
        </HudPanel>
      </section>

      {/* TacticalCard Demo */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground">TacticalCard</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TacticalCard
            title="Strike Mode"
            description="Aggressive intraday scanning"
            icon={<Lightning size={24} className="text-warning" />}
          />
          <TacticalCard
            title="Recon Mode"
            description="Balanced multi-timeframe analysis"
            icon={<Target size={24} className="text-primary" />}
            selected={true}
          />
        </div>
      </section>

      {/* MissionBrief Demo */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground">MissionBrief</h2>
        <MissionBrief title="Tactical Intel">
          <p>This component highlights important information with a holographic border accent.</p>
          <p className="mt-2 text-muted-foreground text-xs">
            Perfect for warnings, summaries, or key intel briefings.
          </p>
        </MissionBrief>
      </section>

      {/* TargetReticleOverlay Demo */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-foreground">TargetReticleOverlay</h2>
        <TargetReticleOverlay className="inline-flex items-center justify-center p-8">
          <div className="text-center">
            <Crosshair size={48} className="text-primary mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Target Acquired</p>
          </div>
        </TargetReticleOverlay>
      </section>
    </div>
  );
}

export default HudComponentsDemo;

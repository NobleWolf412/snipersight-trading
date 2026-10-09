import { FooterStatus,PageHead } from '@/components/hud';
import { MLPanel } from './ResearchPanel';

export function Drills() {
  return <div className="page">
    <PageHead title="Research tools" subtitle="Experimental model tools, separate from execution records" />
    <p>Research only. Model accuracy is not a trading win probability. Live promotion is unavailable.
      Training, reset and log clearing require explicit actions below.</p>
    <MLPanel />
    <FooterStatus />
  </div>;
}

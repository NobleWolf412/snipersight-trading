import { cn } from "@/lib/utils";

interface TargetReticleOverlayProps {
  className?: string;
  children?: React.ReactNode;
}

export function TargetReticleOverlay({ className, children }: TargetReticleOverlayProps) {
  return (
    <div className={cn("target-reticle", className)}>
      {children}
    </div>
  );
}

export default TargetReticleOverlay;

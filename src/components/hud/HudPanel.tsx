import { cn } from "@/lib/utils";

interface HudPanelProps {
  title?: string;
  subtitle?: string;
  className?: string;
  children: React.ReactNode;
}

export function HudPanel({ title, subtitle, className, children }: HudPanelProps) {
  return (
    <div className={cn("command-panel", className)}>
      {(title || subtitle) && (
        <div className="px-6 py-4 border-b border-border/50">
          {title && (
            <h2 className="text-xl font-bold tracking-wide text-primary uppercase">
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
          )}
        </div>
      )}
      <div className="p-6">
        {children}
      </div>
    </div>
  );
}

export default HudPanel;

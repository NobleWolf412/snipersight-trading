import { cn } from "@/lib/utils";

interface HudPanelProps {
  title?: string;
  subtitle?: string;
  className?: string;
  titleClassName?: string;
  children: React.ReactNode;
}

export function HudPanel({ title, subtitle, className, titleClassName, children }: HudPanelProps) {
  return (
    <div className={cn("command-panel", className)}>
      {(title || subtitle) && (
        <div className="px-6 py-5 border-b border-border/50">
          {title && (
            <h2 className={cn("hud-headline text-sm md:text-base tracking-[0.18em] text-slate-200 leading-relaxed", titleClassName)}>
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="text-sm md:text-base text-muted-foreground mt-2">{subtitle}</p>
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

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
    <div className={cn("command-panel relative z-[1] flex flex-col", className)}>
      {(title || subtitle) && (
        <div className="relative z-10 px-6 py-5 border-b border-border/50 flex-shrink-0">
          {title && (
            <h2 className={cn("hud-headline text-xl md:text-2xl lg:text-3xl tracking-[0.18em] text-slate-200 leading-relaxed", titleClassName)}>
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="text-base md:text-lg lg:text-xl text-muted-foreground mt-2">{subtitle}</p>
          )}
        </div>
      )}
      <div className="relative z-10 p-6 flex-1 min-h-0">
        {children}
      </div>
    </div>
  );
}

export default HudPanel;

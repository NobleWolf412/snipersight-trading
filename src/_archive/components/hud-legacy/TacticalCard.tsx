import { cn } from "@/lib/utils";

interface TacticalCardProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
  children?: React.ReactNode;
}

export function TacticalCard({
  title,
  description,
  icon,
  selected = false,
  onClick,
  className,
  children,
}: TacticalCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "tactical-card relative rounded-xl overflow-visible",
        selected && "holo-border hud-glow-green ring-2 ring-primary/50",
        onClick && "cursor-pointer",
        className
      )}
    >
      <div className="relative z-10 px-5 py-4 md:px-7 md:py-5 space-y-3">
        <div className="flex items-start gap-4">
          {icon && (
            <div className="flex-shrink-0 text-primary">
              {icon}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h3 className="hud-headline text-base md:text-lg lg:text-xl tracking-[0.18em] text-foreground mb-1">
              {title}
            </h3>
            {description && (
              <p className="text-sm md:text-base lg:text-lg text-muted-foreground">
                {description}
              </p>
            )}
          </div>
        </div>
        {children && (
          <div>
            {children}
          </div>
        )}
      </div>
    </div>
  );
}

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
        "tactical-card",
        selected && "holo-border hud-glow-green ring-2 ring-primary/50",
        onClick && "cursor-pointer",
        className
      )}
    >
      <div className="flex items-start gap-4">
        {icon && (
          <div className="flex-shrink-0 text-primary">
            {icon}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-lg text-foreground mb-1">
            {title}
          </h3>
          {description && (
            <p className="text-sm text-muted-foreground">
              {description}
            </p>
          )}
          {children && (
            <div className="mt-3">
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TacticalCard;

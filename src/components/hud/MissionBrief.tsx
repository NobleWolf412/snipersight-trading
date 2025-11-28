import { cn } from "@/lib/utils";

interface MissionBriefProps {
  title?: string;
  className?: string;
  children: React.ReactNode;
}

export function MissionBrief({ title, className, children }: MissionBriefProps) {
  return (
    <div className={cn("mission-brief", className)}>
      {title && (
        <h3 className="text-sm font-bold text-emerald-700 dark:text-primary uppercase tracking-wider mb-2">
          {title}
        </h3>
      )}
      <div className="text-sm text-slate-800 dark:text-foreground/90">
        {children}
      </div>
    </div>
  );
}

export default MissionBrief;

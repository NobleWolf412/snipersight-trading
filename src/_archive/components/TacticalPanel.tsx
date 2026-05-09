import React from "react";

interface TacticalPanelProps {
  children: React.ReactNode;
  className?: string;
}

export function TacticalPanel({ children, className = "" }: TacticalPanelProps) {
  return (
    <div className={`relative metal-panel rounded-2xl overflow-hidden ${className}`}>
      <div className="pointer-events-none absolute inset-0">
        <span className="metal-rivet absolute left-4 top-4" />
        <span className="metal-rivet absolute right-4 top-4" />
        <span className="metal-rivet absolute left-4 bottom-4" />
        <span className="metal-rivet absolute right-4 bottom-4" />
      </div>
      {children}
    </div>
  );
}

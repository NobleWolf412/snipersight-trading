import { ReactNode } from "react";

interface PageShellProps {
  children: ReactNode;
  className?: string;
}

/**
 * PageShell - Root page wrapper with standardized padding and max-width
 * 
 * Provides consistent horizontal padding (px-4 → px-6 → px-8 → px-10)
 * and vertical spacing (py-10 → py-16) across all breakpoints.
 * Content is centered with max-w-[1600px] for optimal readability on large displays.
 * 
 * Use this for full-page layouts that need the standard grid frame.
 */
export function PageShell({ children, className = "" }: PageShellProps) {
  return (
    <div className={`w-full px-4 sm:px-6 md:px-8 lg:px-10 py-10 md:py-16 max-w-[1600px] mx-auto ${className}`}>
      {children}
    </div>
  );
}

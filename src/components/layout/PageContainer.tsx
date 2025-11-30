import { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
  wide?: boolean; // optional future use
  className?: string;
  id?: string;
}

// Centers content at a consistent max width for interior app pages.
export function PageContainer({ children, wide = false, className = '', id }: PageContainerProps) {
  return (
    <div
      id={id}
      className={
        (wide ? 'max-w-7xl' : 'max-w-6xl') +
        ' mx-auto px-4 sm:px-6 ' +
        className
      }
    >
      {children}
    </div>
  );
}

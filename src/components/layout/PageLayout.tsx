import { ReactNode } from 'react';

interface PageLayoutProps {
  children: ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '4xl' | '6xl' | '7xl';
  className?: string;
}

const maxWidthClasses = {
  sm: 'max-w-2xl',
  md: 'max-w-3xl',
  lg: 'max-w-4xl',
  xl: 'max-w-5xl',
  '2xl': 'max-w-6xl',
  '4xl': 'max-w-7xl',
  '6xl': 'max-w-6xl',
  '7xl': 'max-w-7xl',
};

export function PageLayout({ children, maxWidth = '2xl', className = '' }: PageLayoutProps) {
  return (
    <div className={`${maxWidthClasses[maxWidth]} mx-auto px-6 py-12 ${className}`}>
      {children}
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, icon, actions, className = '' }: PageHeaderProps) {
  return (
    <div className={`flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between ${className}`}>
      <div className="space-y-3">
        <h1 className="text-4xl font-bold text-foreground flex items-center gap-4">
          {icon}
          {title}
        </h1>
        {description && (
          <p className="text-base text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-3">
          {actions}
        </div>
      )}
    </div>
  );
}

interface PageSectionProps {
  children: ReactNode;
  title?: string;
  description?: string;
  className?: string;
}

export function PageSection({ children, title, description, className = '' }: PageSectionProps) {
  return (
    <section className={`space-y-6 ${className}`}>
      {(title || description) && (
        <div className="space-y-2">
          {title && (
            <h2 className="text-sm font-bold text-muted-foreground tracking-wider uppercase">
              {title}
            </h2>
          )}
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}



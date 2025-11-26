import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface AnimatedCardProps {
  className?: string;
  title?: string;
  description?: string;
  children?: React.ReactNode;
}

export function AnimatedCard({ className, title, description, children }: AnimatedCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      transition={{ type: 'spring', stiffness: 260, damping: 20 }}
      className={cn(
        'rounded-xl border border-neutral-6/40 bg-bg/70 backdrop-blur p-4 shadow-[0_8px_30px_rgb(0,0,0,0.12)]',
        'hover:shadow-[0_12px_40px_rgba(16,185,129,0.18)] transition-all',
        'animate-in fade-in slide-in-from-bottom-1',
        className,
      )}
    >
      {(title || description) && (
        <div className="mb-2">
          {title && <h3 className="text-lg font-semibold tracking-wide">{title}</h3>}
          {description && <p className="text-sm text-fg/70">{description}</p>}
        </div>
      )}
      <div>{children}</div>
    </motion.div>
  );
}

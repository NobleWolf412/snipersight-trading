import { toast as sonnerToast } from 'sonner';

export function useToast() {
  return {
    toast: (title: string | { title?: string; description?: string; variant?: string }, options?: { description?: string }) => {
      if (typeof title === 'string') {
        sonnerToast(title, options);
      } else {
        const { title: toastTitle, description, variant } = title;
        
        if (variant === 'destructive') {
          sonnerToast.error(toastTitle || 'Error', {
            description,
          });
        } else {
          sonnerToast(toastTitle || '', {
            description,
          });
        }
      }
    },
  };
}

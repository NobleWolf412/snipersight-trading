import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { ScanResult } from '@/utils/mockData';

interface DetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: ScanResult;
}

export function DetailsModal({ isOpen, onClose, result }: DetailsModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>Signal Details: {result.pair}</DialogTitle>
          <DialogDescription>Complete analysis output</DialogDescription>
        </DialogHeader>

        <ScrollArea className="h-[600px] pr-4">
          <pre className="bg-card border border-border rounded-lg p-4 text-xs font-mono overflow-x-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

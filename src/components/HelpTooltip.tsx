import { Info } from '@phosphor-icons/react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface HelpTooltipProps {
    content: string;
    example?: string;
    warning?: string;
    className?: string;
    iconSize?: number;
}

/**
 * HelpTooltip - Contextual help icon with tooltip
 * 
 * Shows an info icon that displays helpful guidance on hover.
 * Supports optional examples and warnings.
 */
export function HelpTooltip({
    content,
    example,
    warning,
    className,
    iconSize = 14
}: HelpTooltipProps) {
    return (
        <Tooltip delayDuration={200}>
            <TooltipTrigger asChild>
                <button
                    type="button"
                    className={cn(
                        "inline-flex items-center justify-center text-muted-foreground hover:text-primary transition-colors ml-1.5 cursor-help",
                        className
                    )}
                    aria-label="Show help"
                >
                    <Info size={iconSize} weight="regular" />
                </button>
            </TooltipTrigger>
            <TooltipContent
                side="top"
                className="max-w-xs bg-background/95 backdrop-blur border border-border shadow-xl p-3"
                sideOffset={5}
            >
                <div className="space-y-2 text-sm">
                    <p className="text-foreground">{content}</p>

                    {example && (
                        <p className="text-muted-foreground text-xs border-l-2 border-primary/40 pl-2">
                            💡 {example}
                        </p>
                    )}

                    {warning && (
                        <p className="text-warning text-xs font-medium">
                            {warning}
                        </p>
                    )}
                </div>
            </TooltipContent>
        </Tooltip>
    );
}

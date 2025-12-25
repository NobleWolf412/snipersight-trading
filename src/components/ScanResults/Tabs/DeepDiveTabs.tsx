
import { ScanResult } from '@/utils/mockData';
import { Button } from '@/components/ui/button';
import { ConfluenceVisualizer } from './ConfluenceVisualizer';

interface TabProps {
    signal: ScanResult;
    metadata?: any;
}

export function ChartAnalytics({ signal }: TabProps) {
    return (
        <div className="h-full w-full flex items-center justify-center bg-black/20 text-muted-foreground font-mono animate-in fade-in">
            <div className="text-center space-y-4">
                <h1 className="text-4xl font-bold text-white opacity-20">CHART ANALYTICS</h1>
                <p>Advanced charting module initializing for {signal.pair}...</p>
                <Button variant="outline">LOAD CHART DATA</Button>
            </div>
        </div>
    );
}

export function ConfluenceBreakdown({ signal }: TabProps) {
    return <ConfluenceVisualizer signal={signal} />;
}

export function TechAnalysis({ signal }: TabProps) {
    return (
        <div className="h-full w-full flex items-center justify-center bg-black/20 text-muted-foreground font-mono animate-in fade-in">
            <div className="text-center space-y-4">
                <h1 className="text-4xl font-bold text-white opacity-20">DEEP DIVE ANALYTICS</h1>
                <p>Processing OB/Liquidity data for {signal.pair}...</p>
            </div>
        </div>
    );
}

export function SignalReasoning({ signal }: TabProps) {
    return (
        <div className="h-full w-full flex items-center justify-center bg-black/20 text-muted-foreground font-mono animate-in fade-in">
            <div className="text-center space-y-4">
                <h1 className="text-4xl font-bold text-white opacity-20">STRATEGIC REASONING</h1>
                <p>Generating trade thesis for {signal.pair}...</p>
            </div>
        </div>
    );
}

export function IndicatorStatus({ signal }: TabProps) {
    return (
        <div className="h-full w-full flex items-center justify-center bg-black/20 text-muted-foreground font-mono animate-in fade-in">
            <div className="text-center space-y-4">
                <h1 className="text-4xl font-bold text-white opacity-20">SYSTEM STATUS</h1>
                <p>Checking indicator matrix for {signal.pair}...</p>
            </div>
        </div>
    );
}

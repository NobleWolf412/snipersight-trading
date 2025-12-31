
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Newspaper, ArrowUpRight } from '@phosphor-icons/react';

interface NewsItem {
    id: string;
    source: string;
    title: string;
    url: string;
    sentiment: 'bullish' | 'bearish' | 'neutral';
    time: string;
}

const MOCK_NEWS: NewsItem[] = [
    { id: '1', source: 'CoinDesk', title: 'Bitcoin Hashrate Hits New All-Time High Amidst Miner CAPEX Boom', url: '#', sentiment: 'bullish', time: '10m ago' },
    { id: '2', source: 'Camel Finance', title: 'Structural Cycle Analysis: 4YC Right Translation Confirmed', url: '#', sentiment: 'bullish', time: '25m ago' },
    { id: '3', source: 'The Block', title: 'SEC Delays ETF Decision, Market Shrugs Off Regulatory Noise', url: '#', sentiment: 'neutral', time: '1h ago' },
    { id: '4', source: 'Decrypt', title: 'DeFi TVL Surges 15% as Yield Farmers Return to Ethereum', url: '#', sentiment: 'bullish', time: '2h ago' },
    { id: '5', source: 'MacroScope', title: 'DXY Showing Signs of Weakness at Key Resistance', url: '#', sentiment: 'bullish', time: '3h ago' },
];

export function NewsTicker() {
    const [isPaused, setIsPaused] = useState(false);

    return (
        <div
            className="w-full bg-card/20 border-y border-border/40 backdrop-blur-sm overflow-hidden flex items-center h-10"
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
        >
            <div className="flex-shrink-0 px-4 h-full flex items-center bg-card/40 border-r border-border/40 z-20">
                <Newspaper className="text-accent mr-2" size={16} weight="duotone" />
                <span className="text-xs font-bold font-mono text-accent uppercase tracking-widest">Live Wire</span>
            </div>

            <div className="flex-1 overflow-hidden relative group">
                <div className={cn(
                    "flex whitespace-nowrap animate-marquee hover:pause",
                    isPaused && "play-paused"
                )}>
                    {[...MOCK_NEWS, ...MOCK_NEWS].map((item, i) => (
                        <div key={`${item.id}-${i}`} className="inline-flex items-center mx-8 group/item">
                            <span className="text-[10px] font-mono text-muted-foreground mr-2">[{item.time}]</span>
                            <span className={cn(
                                "text-xs font-medium mr-2",
                                item.sentiment === 'bullish' ? "text-green-400" :
                                    item.sentiment === 'bearish' ? "text-red-400" : "text-foreground"
                            )}>
                                {item.source}:
                            </span>
                            <a href={item.url} className="text-xs text-muted-foreground hover:text-accent transition-colors flex items-center gap-1">
                                {item.title}
                                <ArrowUpRight size={10} className="opacity-0 group-hover/item:opacity-100 transition-opacity" />
                            </a>
                        </div>
                    ))}
                </div>
            </div>

            {/* Fade overlay for right edge */}
            <div className="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
        </div>
    );
}

import { useEffect, useState, useRef, type ReactElement } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  CheckCircle, 
  XCircle, 
  Warning, 
  Info, 
  Target, 
  TrendUp,
  TrendDown,
  Activity,
  Pause,
  Play
} from '@phosphor-icons/react';
import { telemetryService, type TelemetryEvent } from '@/services/telemetryService';
import { formatDistanceToNow } from 'date-fns';

interface ActivityFeedProps {
  limit?: number;
  autoScroll?: boolean;
  showFilters?: boolean;
  pollInterval?: number;
}

export function ActivityFeed({
  limit = 100,
  autoScroll = true,
  showFilters = true,
  pollInterval = 3000
}: ActivityFeedProps) {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [filteredEvents, setFilteredEvents] = useState<TelemetryEvent[]>([]);
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('all');
  const [isPaused, setIsPaused] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Initial load
  useEffect(() => {
    const loadInitialEvents = async () => {
      console.log('[ActivityFeed] Loading initial events, limit:', limit);
      try {
        const response = await telemetryService.getRecentEvents(limit);
        console.log('[ActivityFeed] Loaded events:', response.events.length);
        setEvents(response.events);
        setIsLoading(false);
      } catch (error) {
        console.error('[ActivityFeed] Failed to load initial events:', error);
        setIsLoading(false);
      }
    };

    loadInitialEvents();
  }, [limit]);

  // Polling for new events
  useEffect(() => {
    if (isPaused) {
      console.log('[ActivityFeed] Polling paused');
      telemetryService.stopPolling();
      return;
    }

    console.log('[ActivityFeed] Starting polling, interval:', pollInterval);
    telemetryService.startPolling((newEvents) => {
      if (newEvents.length > 0) {
        console.log('[ActivityFeed] Received new events:', newEvents.length);
      }
      setEvents((prev) => {
        // Merge new events, avoiding duplicates
        const existingIds = new Set(prev.map(e => e.id));
        const uniqueNewEvents = newEvents.filter(e => !existingIds.has(e.id));
        
        // Combine and sort by timestamp (newest first)
        const combined = [...uniqueNewEvents, ...prev];
        combined.sort((a, b) => 
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
        
        // Keep only most recent N events
        return combined.slice(0, limit);
      });
    }, pollInterval);

    return () => {
      telemetryService.stopPolling();
    };
  }, [isPaused, limit, pollInterval]);

  // Filter events
  useEffect(() => {
    if (eventTypeFilter === 'all') {
      setFilteredEvents(events);
    } else {
      setFilteredEvents(events.filter(e => e.event_type === eventTypeFilter));
    }
  }, [events, eventTypeFilter]);

  // Auto scroll
  useEffect(() => {
    if (autoScroll && !isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [filteredEvents, autoScroll, isPaused]);

  const togglePause = () => {
    setIsPaused(!isPaused);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-lg font-bold flex items-center gap-2">
          <Activity size={20} weight="bold" />
          Activity Feed
        </CardTitle>
        <div className="flex items-center gap-2">
          {showFilters && (
            <Select value={eventTypeFilter} onValueChange={setEventTypeFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Events</SelectItem>
                <SelectItem value="scan_started">Scans Started</SelectItem>
                <SelectItem value="scan_completed">Scans Completed</SelectItem>
                <SelectItem value="signal_generated">Signals Generated</SelectItem>
                <SelectItem value="signal_rejected">Signals Rejected</SelectItem>
                <SelectItem value="alt_stop_suggested">Alt Stop Suggested</SelectItem>
                <SelectItem value="error_occurred">Errors</SelectItem>
              </SelectContent>
            </Select>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={togglePause}
            className="flex items-center gap-2"
          >
            {isPaused ? <Play size={16} weight="fill" /> : <Pause size={16} weight="fill" />}
            {isPaused ? 'Resume' : 'Pause'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[600px]" ref={scrollRef}>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading activity...
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No activity yet. Run a scan to see events here.
            </div>
          ) : (
            <div className="space-y-2">
              {filteredEvents.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function EventCard({ event }: { event: TelemetryEvent }) {
  const { icon, color, title, description } = getEventDisplay(event);
  const timeAgo = formatDistanceToNow(new Date(event.timestamp), { addSuffix: true });

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border border-border bg-card/50 hover:bg-card transition-colors">
      <div className={`p-2 rounded-full ${color}`}>
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold">{title}</p>
          <span className="text-xs text-muted-foreground whitespace-nowrap">{timeAgo}</span>
        </div>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
        {event.symbol && (
          <Badge variant="outline" className="mt-2 text-xs">
            {event.symbol}
          </Badge>
        )}
      </div>
    </div>
  );
}

function getEventDisplay(event: TelemetryEvent): {
  icon: ReactElement;
  color: string;
  title: string;
  description: string;
} {
  const data = event.data || {};

  switch (event.event_type) {
    case 'scan_started':
      return {
        icon: <Target size={20} weight="bold" />,
        color: 'bg-blue-500/20 text-blue-400',
        title: 'Scan Started',
        description: `Scanning ${data.symbol_count || 0} symbols with ${data.profile || 'unknown'} profile`
      };

    case 'scan_completed':
      return {
        icon: <CheckCircle size={20} weight="fill" />,
        color: 'bg-green-500/20 text-green-400',
        title: 'Scan Completed',
        description: `${data.signals_generated || 0} signals generated, ${data.signals_rejected || 0} rejected (${data.duration_seconds?.toFixed(1)}s)`
      };

    case 'signal_generated':
      const direction = data.direction || 'UNKNOWN';
      const isLong = direction === 'LONG';
      return {
        icon: isLong ? <TrendUp size={20} weight="bold" /> : <TrendDown size={20} weight="bold" />,
        color: isLong ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400',
        title: `${direction} Signal Generated`,
        description: `${data.setup_type || 'Setup'} • Confidence: ${data.confidence_score}% • R:R ${data.risk_reward_ratio || 0}`
      };

    case 'signal_rejected':
      return {
        icon: <XCircle size={20} weight="fill" />,
        color: 'bg-orange-500/20 text-orange-400',
        title: 'Signal Rejected',
        description: data.reason || 'Failed quality gate'
      };

    case 'alt_stop_suggested':
      return {
        icon: <Warning size={20} weight="fill" />,
        color: 'bg-amber-500/20 text-amber-400',
        title: 'Alt Stop Suggested',
        description: `Cushion ${typeof data.cushion_pct === 'number' ? data.cushion_pct.toFixed(2) : '?'}% (${data.risk_band || 'unknown'}) → ${typeof data.suggested_level === 'number' ? data.suggested_level : 'n/a'}`
      };

    case 'error_occurred':
      return {
        icon: <Warning size={20} weight="fill" />,
        color: 'bg-red-500/20 text-red-400',
        title: 'Error Occurred',
        description: data.error_message || 'An error occurred'
      };

    default:
      return {
        icon: <Info size={20} weight="fill" />,
        color: 'bg-gray-500/20 text-gray-400',
        title: event.event_type.replace(/_/g, ' ').toUpperCase(),
        description: JSON.stringify(data)
      };
  }
}

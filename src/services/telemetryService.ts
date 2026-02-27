/**
 * Telemetry Service
 * 
 * Client for fetching telemetry events and analytics from backend.
 * Supports polling for real-time updates.
 */

import { api } from './api';

export interface TelemetryEvent {
  id: number;
  event_type: string;
  timestamp: string;
  run_id?: string;
  symbol?: string;
  data?: Record<string, any>;
}

export interface TelemetryResponse {
  events: TelemetryEvent[];
  count: number;
}

export interface TelemetryAnalytics {
  metrics: {
    total_scans: number;
    total_signals_generated: number;
    total_signals_rejected: number;
    total_errors: number;
    signal_success_rate: number;
  };
  rejection_breakdown: Record<string, number>;
  time_range: {
    start?: string;
    end?: string;
  };
}

export interface TelemetryPagination {
  events: TelemetryEvent[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

class TelemetryService {
  private pollingInterval: number | null = null;
  private lastEventId: number | null = null;

  /**
   * Get recent telemetry events for real-time display
   */
  async getRecentEvents(limit: number = 100, sinceId?: number): Promise<TelemetryResponse> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (sinceId) {
      params.append('since_id', sinceId.toString());
    }

    const response = await fetch(`${api.baseURL}/telemetry/recent?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch recent events: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Query telemetry events with filters
   */
  async queryEvents(filters: {
    limit?: number;
    offset?: number;
    event_type?: string;
    symbol?: string;
    run_id?: string;
    start_time?: string;
    end_time?: string;
  } = {}): Promise<TelemetryPagination> {
    const params = new URLSearchParams();
    
    if (filters.limit) params.append('limit', filters.limit.toString());
    if (filters.offset) params.append('offset', filters.offset.toString());
    if (filters.event_type) params.append('event_type', filters.event_type);
    if (filters.symbol) params.append('symbol', filters.symbol);
    if (filters.run_id) params.append('run_id', filters.run_id);
    if (filters.start_time) params.append('start_time', filters.start_time);
    if (filters.end_time) params.append('end_time', filters.end_time);

    const response = await fetch(`${api.baseURL}/telemetry/events?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to query events: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get aggregated analytics metrics
   */
  async getAnalytics(startTime?: string, endTime?: string): Promise<TelemetryAnalytics> {
    const params = new URLSearchParams();
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);

    const response = await fetch(`${api.baseURL}/telemetry/analytics?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch analytics: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Start polling for new events
   */
  startPolling(callback: (events: TelemetryEvent[]) => void, intervalMs: number = 3000) {
    this.stopPolling(); // Clear any existing interval

    // Initial fetch
    this.pollOnce(callback);

    // Set up recurring polling
    this.pollingInterval = window.setInterval(() => {
      this.pollOnce(callback);
    }, intervalMs);
  }

  /**
   * Poll once for new events
   */
  private async pollOnce(callback: (events: TelemetryEvent[]) => void) {
    try {
      const response = await this.getRecentEvents(100, this.lastEventId || undefined);
      
      if (response.events.length > 0) {
        // Update last event ID
        const maxId = Math.max(...response.events.map(e => e.id));
        this.lastEventId = maxId;

        // Callback with new events
        callback(response.events);
      }
    } catch (error) {
      console.error('Polling error:', error);
    }
  }

  /**
   * Stop polling for events
   */
  stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  /**
   * Reset polling state (e.g., when changing filters)
   */
  resetPolling() {
    this.lastEventId = null;
    this.stopPolling();
  }
}

// Singleton instance
export const telemetryService = new TelemetryService();

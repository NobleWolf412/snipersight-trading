/**
 * Notification Polling Service
 * 
 * Polls backend for new notification events and integrates
 * with the browser notification system.
 */

import { notificationManager } from './notifications';

interface NotificationEvent {
  id: string;
  type: 'signal' | 'risk_alert' | 'execution' | 'system';
  priority: 'low' | 'normal' | 'high' | 'critical';
  timestamp: string;
  title: string;
  body: string;
  data?: any;
}

interface NotificationResponse {
  events: NotificationEvent[];
  count: number;
  timestamp: string;
}

class NotificationPollingService {
  private pollingInterval: number = 5000; // 5 seconds
  private isPolling: boolean = false;
  private intervalId: number | null = null;
  private lastFetchTimestamp: string | null = null;
  private baseUrl = '/api';

  constructor() {
    this.setupVisibilityListener();
  }

  /**
   * Start polling for notifications
   */
  startPolling() {
    if (this.isPolling) {
      console.log('📡 Notification polling already active');
      return;
    }

    this.isPolling = true;
    console.log('📡 Starting notification polling...');

    // Initial fetch
    this.fetchNotifications();

    // Set up polling interval
    this.intervalId = window.setInterval(() => {
      this.fetchNotifications();
    }, this.pollingInterval);
  }

  /**
   * Stop polling for notifications
   */
  stopPolling() {
    if (!this.isPolling) {
      return;
    }

    this.isPolling = false;
    console.log('📡 Stopping notification polling');

    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Fetch notifications from backend
   */
  private async fetchNotifications() {
    try {
      const url = new URL(`${this.baseUrl}/notifications`, window.location.origin);
      
      // Add since parameter if we have a last fetch timestamp
      if (this.lastFetchTimestamp) {
        url.searchParams.set('since', this.lastFetchTimestamp);
      }
      
      url.searchParams.set('limit', '20');

      const response = await fetch(url.toString());
      
      if (!response.ok) {
        throw new Error(`Failed to fetch notifications: ${response.status}`);
      }

      const data: NotificationResponse = await response.json();
      
      // Process new events
      if (data.events.length > 0) {
        console.log(`📡 Received ${data.events.length} notification events`);
        this.processNotificationEvents(data.events);
      }

      // Update last fetch timestamp
      this.lastFetchTimestamp = data.timestamp;

    } catch (error) {
      console.error('❌ Failed to fetch notifications:', error);
      
      // Don't spam notifications about polling errors
      if (Math.random() < 0.1) { // Only 10% chance to show error
        notificationManager.notifySystem({
          title: '⚠️ Notification Service Unavailable',
          body: 'Unable to fetch real-time notifications',
          priority: 'low'
        });
      }
    }
  }

  /**
   * Process notification events from backend
   */
  private processNotificationEvents(events: NotificationEvent[]) {
    // Sort events by timestamp (oldest first) to process in order
    const sortedEvents = events.sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    for (const event of sortedEvents) {
      this.handleNotificationEvent(event);
    }
  }

  /**
   * Handle individual notification event
   */
  private handleNotificationEvent(event: NotificationEvent) {
    console.log(`📱 Processing notification: ${event.type} - ${event.title}`);

    switch (event.type) {
      case 'signal':
        if (event.data) {
          notificationManager.notifyHighConfidenceSignal({
            symbol: event.data.symbol || 'UNKNOWN',
            direction: event.data.direction || 'UNKNOWN',
            confidence: event.data.confidence || 0,
            entry: event.data.entry || 0,
            riskReward: event.data.risk_reward || 0
          });
        }
        break;

      case 'risk_alert':
        if (event.data) {
          notificationManager.notifyRiskAlert({
            type: event.data.alert_type || 'unknown',
            message: event.body,
            severity: event.data.severity || 'warning'
          });
        }
        break;

      case 'execution':
        if (event.data) {
          notificationManager.notifyOrderExecution({
            symbol: event.data.symbol || 'UNKNOWN',
            side: event.data.side || 'BUY',
            quantity: event.data.quantity || 0,
            price: event.data.price || 0,
            status: event.data.status || 'unknown'
          });
        }
        break;

      case 'system':
        notificationManager.notifySystem({
          title: event.title,
          body: event.body,
          priority: event.priority,
          action: event.data?.action
        });
        break;

      default:
        console.warn('Unknown notification type:', event.type);
        break;
    }
  }

  /**
   * Set polling interval
   */
  setPollingInterval(intervalMs: number) {
    if (intervalMs < 1000) {
      console.warn('Polling interval too low, minimum is 1 second');
      return;
    }

    this.pollingInterval = intervalMs;
    console.log(`📡 Polling interval set to ${intervalMs}ms`);

    // Restart polling if active
    if (this.isPolling) {
      this.stopPolling();
      this.startPolling();
    }
  }

  /**
   * Setup page visibility listener to pause/resume polling
   */
  private setupVisibilityListener() {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        // Page became visible - resume polling
        if (!this.isPolling) {
          console.log('📡 Page visible - resuming notification polling');
          this.startPolling();
        }
      } else {
        // Page hidden - pause polling to save resources
        if (this.isPolling) {
          console.log('📡 Page hidden - pausing notification polling');
          this.stopPolling();
        }
      }
    });
  }

  /**
   * Manual fetch of latest notifications
   */
  async fetchLatest() {
    console.log('📡 Manual notification fetch requested');
    await this.fetchNotifications();
  }

  /**
   * Get polling status
   */
  getStatus() {
    return {
      isPolling: this.isPolling,
      pollingInterval: this.pollingInterval,
      lastFetchTimestamp: this.lastFetchTimestamp
    };
  }

  /**
   * Clear notification history on backend
   */
  async clearAllNotifications() {
    try {
      const response = await fetch(`${this.baseUrl}/notifications`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error(`Failed to clear notifications: ${response.status}`);
      }

      console.log('🗑️ Cleared all notifications on backend');
      this.lastFetchTimestamp = null;

    } catch (error) {
      console.error('❌ Failed to clear notifications:', error);
      throw error;
    }
  }
}

export const notificationPollingService = new NotificationPollingService();
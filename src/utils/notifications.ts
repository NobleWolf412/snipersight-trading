/**
 * Browser Notification System for SniperSight Trading
 * 
 * Handles critical trading event notifications with permission management,
 * notification queuing, and integration with the existing toast system.
 */

interface NotificationConfig {
  title: string;
  body: string;
  icon?: string;
  badge?: string;
  tag?: string;
  requireInteraction?: boolean;
  silent?: boolean;
  data?: any;
}

interface NotificationPermissionState {
  granted: boolean;
  denied: boolean;
  default: boolean;
}

type NotificationPriority = 'low' | 'normal' | 'high' | 'critical';

interface TradingNotification {
  id: string;
  type: 'signal' | 'risk_alert' | 'execution' | 'system';
  priority: NotificationPriority;
  timestamp: Date;
  config: NotificationConfig;
  acknowledged: boolean;
}

class BrowserNotificationManager {
  private isEnabled: boolean = false;
  private permission: NotificationPermissionState = {
    granted: false,
    denied: false,
    default: true
  };
  private notificationQueue: TradingNotification[] = [];
  private activeNotifications: Map<string, Notification> = new Map();
  private maxActiveNotifications = 5;
  private soundEnabled = true;

  constructor() {
    this.checkPermission();
    this.setupVisibilityListener();
  }

  /**
   * Initialize notification system and request permissions
   */
  async initialize(): Promise<boolean> {
    try {
      if (!('Notification' in window)) {
        console.warn('Browser notifications not supported');
        return false;
      }

      if (Notification.permission === 'denied') {
        this.permission.denied = true;
        return false;
      }

      const permission = await this.requestPermission();
      if (permission === 'granted') {
        this.isEnabled = true;
        console.log('✅ Browser notifications enabled');
        return true;
      } else {
        console.warn('⚠️ Notification permission denied');
        return false;
      }
    } catch (error) {
      console.error('❌ Failed to initialize notifications:', error);
      return false;
    }
  }

  /**
   * Request notification permission from user
   */
  private async requestPermission(): Promise<NotificationPermission> {
    if (Notification.permission === 'granted') {
      this.permission.granted = true;
      return 'granted';
    }

    if (Notification.permission === 'denied') {
      this.permission.denied = true;
      return 'denied';
    }

    // Request permission
    const permission = await Notification.requestPermission();
    this.updatePermissionState(permission);
    return permission;
  }

  private updatePermissionState(permission: NotificationPermission) {
    this.permission = {
      granted: permission === 'granted',
      denied: permission === 'denied',
      default: permission === 'default'
    };
  }

  private checkPermission() {
    if ('Notification' in window) {
      this.updatePermissionState(Notification.permission);
    }
  }

  /**
   * Send high-confidence trading signal notification
   */
  notifyHighConfidenceSignal(signal: {
    symbol: string;
    direction: string;
    confidence: number;
    entry: number;
    riskReward: number;
  }) {
    const notification: TradingNotification = {
      id: `signal-${signal.symbol}-${Date.now()}`,
      type: 'signal',
      priority: 'high',
      timestamp: new Date(),
      acknowledged: false,
      config: {
        title: `🎯 High-Confidence Setup: ${signal.symbol}`,
        body: `${signal.direction} • ${signal.confidence.toFixed(1)}% confidence • ${signal.riskReward.toFixed(1)}:1 R:R • Entry: $${signal.entry.toFixed(2)}`,
        icon: '/icons/signal-icon.png',
        badge: '/icons/badge.png',
        tag: `signal-${signal.symbol}`,
        requireInteraction: true,
        data: { signalType: 'signal', ...signal }
      }
    };

    this.queueNotification(notification);
  }

  /**
   * Send risk alert notification
   */
  notifyRiskAlert(alert: {
    type: 'exposure_limit' | 'loss_limit' | 'max_positions' | 'drawdown';
    message: string;
    severity: 'warning' | 'critical';
  }) {
    const notification: TradingNotification = {
      id: `risk-${alert.type}-${Date.now()}`,
      type: 'risk_alert',
      priority: alert.severity === 'critical' ? 'critical' : 'high',
      timestamp: new Date(),
      acknowledged: false,
      config: {
        title: `⚠️ Risk Alert: ${alert.type.replace('_', ' ').toUpperCase()}`,
        body: alert.message,
        icon: '/icons/risk-icon.png',
        badge: '/icons/badge.png',
        tag: `risk-${alert.type}`,
        requireInteraction: alert.severity === 'critical',
        data: { alertType: 'risk_alert', ...alert }
      }
    };

    this.queueNotification(notification);
  }

  /**
   * Send order execution notification
   */
  notifyOrderExecution(execution: {
    symbol: string;
    side: string;
    quantity: number;
    price: number;
    status: 'filled' | 'partial' | 'cancelled' | 'rejected';
  }) {
    const statusEmoji = {
      filled: '✅',
      partial: '🟡',
      cancelled: '❌',
      rejected: '🚫'
    };

    const notification: TradingNotification = {
      id: `execution-${execution.symbol}-${Date.now()}`,
      type: 'execution',
      priority: execution.status === 'rejected' ? 'high' : 'normal',
      timestamp: new Date(),
      acknowledged: false,
      config: {
        title: `${statusEmoji[execution.status]} Order ${execution.status.toUpperCase()}: ${execution.symbol}`,
        body: `${execution.side} ${execution.quantity} @ $${execution.price.toFixed(2)}`,
        icon: '/icons/execution-icon.png',
        badge: '/icons/badge.png',
        tag: `execution-${execution.symbol}`,
        requireInteraction: execution.status === 'rejected',
        data: { type: 'execution', ...execution }
      }
    };

    this.queueNotification(notification);
  }

  /**
   * Send system notification
   */
  notifySystem(message: {
    title: string;
    body: string;
    priority?: NotificationPriority;
    action?: string;
  }) {
    const notification: TradingNotification = {
      id: `system-${Date.now()}`,
      type: 'system',
      priority: message.priority || 'normal',
      timestamp: new Date(),
      acknowledged: false,
      config: {
        title: message.title,
        body: message.body,
        icon: '/icons/system-icon.png',
        badge: '/icons/badge.png',
        tag: 'system',
        requireInteraction: message.priority === 'critical',
        data: { type: 'system', action: message.action }
      }
    };

    this.queueNotification(notification);
  }

  /**
   * Queue notification for display
   */
  private queueNotification(notification: TradingNotification) {
    if (!this.isEnabled || this.permission.denied) {
      console.log('📱 Notification queued (permissions not granted):', notification.config.title);
      return;
    }

    // Add to queue
    this.notificationQueue.push(notification);

    // Process queue
    this.processNotificationQueue();
  }

  /**
   * Process notification queue based on priority
   */
  private processNotificationQueue() {
    if (this.notificationQueue.length === 0) return;

    // Sort by priority (critical -> high -> normal -> low)
    const priorityOrder = { critical: 0, high: 1, normal: 2, low: 3 };
    this.notificationQueue.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);

    // Clear old notifications of same type if queue is full
    if (this.activeNotifications.size >= this.maxActiveNotifications) {
      this.clearOldNotifications();
    }

    // Display next notification
    const nextNotification = this.notificationQueue.shift();
    if (nextNotification) {
      this.displayNotification(nextNotification);
    }
  }

  /**
   * Display browser notification
   */
  private displayNotification(tradingNotification: TradingNotification) {
    try {
      const notification = new Notification(
        tradingNotification.config.title,
        {
          body: tradingNotification.config.body,
          icon: tradingNotification.config.icon,
          badge: tradingNotification.config.badge,
          tag: tradingNotification.config.tag,
          requireInteraction: tradingNotification.config.requireInteraction,
          silent: tradingNotification.config.silent,
          data: tradingNotification.config.data
        }
      );

      // Store reference
      this.activeNotifications.set(tradingNotification.id, notification);

      // Handle click events
      notification.onclick = (event) => {
        this.handleNotificationClick(event, tradingNotification);
      };

      // Auto-close after delay (unless requires interaction)
      if (!tradingNotification.config.requireInteraction) {
        setTimeout(() => {
          notification.close();
          this.activeNotifications.delete(tradingNotification.id);
        }, this.getNotificationDuration(tradingNotification.priority));
      }

      // Handle close event
      notification.onclose = () => {
        this.activeNotifications.delete(tradingNotification.id);
      };

      // Play sound for high priority notifications
      if (tradingNotification.priority === 'high' || tradingNotification.priority === 'critical') {
        this.playNotificationSound(tradingNotification.type);
      }

      console.log('📱 Notification displayed:', tradingNotification.config.title);

    } catch (error) {
      console.error('❌ Failed to display notification:', error);
    }
  }

  /**
   * Handle notification click events
   */
  private handleNotificationClick(event: Event, tradingNotification: TradingNotification) {
    event.preventDefault();

    // Focus the window
    window.focus();

    // Route based on notification type
    switch (tradingNotification.type) {
      case 'signal':
        // Navigate to scanner results
        window.location.hash = '/results';
        break;
      case 'risk_alert':
        // Navigate to portfolio/risk page
        window.location.hash = '/portfolio';
        break;
      case 'execution':
        // Navigate to trading page
        window.location.hash = '/trading';
        break;
      case 'system':
        // Handle system action
        if (tradingNotification.config.data?.action) {
          this.handleSystemAction(tradingNotification.config.data.action);
        }
        break;
    }

    // Mark as acknowledged
    tradingNotification.acknowledged = true;

    // Close the notification
    const notification = this.activeNotifications.get(tradingNotification.id);
    if (notification) {
      notification.close();
    }
  }

  /**
   * Handle system actions from notifications
   */
  private handleSystemAction(action: string) {
    switch (action) {
      case 'refresh':
        window.location.reload();
        break;
      case 'check_connection':
        // Trigger connection check
        window.dispatchEvent(new CustomEvent('check-connection'));
        break;
      default:
        console.log('Unknown system action:', action);
    }
  }

  /**
   * Play notification sound based on type
   */
  private playNotificationSound(type: TradingNotification['type']) {
    if (!this.soundEnabled) return;

    const soundMap = {
      signal: '/sounds/signal.mp3',
      risk_alert: '/sounds/alert.mp3',
      execution: '/sounds/execution.mp3',
      system: '/sounds/notification.mp3'
    };

    const audio = new Audio(soundMap[type]);
    audio.volume = 0.3;
    audio.play().catch(error => {
      console.log('Could not play notification sound:', error);
    });
  }

  /**
   * Get notification display duration based on priority
   */
  private getNotificationDuration(priority: NotificationPriority): number {
    const durations = {
      low: 3000,      // 3 seconds
      normal: 5000,   // 5 seconds
      high: 8000,     // 8 seconds
      critical: 0     // Never auto-close
    };
    return durations[priority];
  }

  /**
   * Clear old notifications to make room for new ones
   */
  private clearOldNotifications() {
    const notifications = Array.from(this.activeNotifications.entries());
    const oldestNotification = notifications[0];

    if (oldestNotification) {
      oldestNotification[1].close();
      this.activeNotifications.delete(oldestNotification[0]);
    }
  }

  /**
   * Setup page visibility listener to handle tab switching
   */
  private setupVisibilityListener() {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        // Page became visible - clear all notifications since user can see the UI
        this.clearAllNotifications();
      }
    });
  }

  /**
   * Clear all active notifications
   */
  clearAllNotifications() {
    this.activeNotifications.forEach(notification => {
      notification.close();
    });
    this.activeNotifications.clear();
  }

  /**
   * Enable/disable sound for notifications
   */
  setSoundEnabled(enabled: boolean) {
    this.soundEnabled = enabled;
  }

  /**
   * Get notification permission status
   */
  getPermissionStatus(): NotificationPermissionState {
    return this.permission;
  }

  /**
   * Check if notifications are enabled
   */
  isNotificationEnabled(): boolean {
    return this.isEnabled && this.permission.granted;
  }

  /**
   * Get notification statistics
   */
  getStats() {
    return {
      enabled: this.isEnabled,
      permission: this.permission,
      activeCount: this.activeNotifications.size,
      queuedCount: this.notificationQueue.length,
      soundEnabled: this.soundEnabled
    };
  }
}

// Create singleton instance
export const notificationManager = new BrowserNotificationManager();

// Export types for use in other components
export type {
  TradingNotification,
  NotificationConfig,
  NotificationPermissionState,
  NotificationPriority
};
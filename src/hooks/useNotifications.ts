/**
 * React Hook for Browser Notifications
 * 
 * Provides React integration for the browser notification system
 * with state management and lifecycle handling.
 */

import { useState, useEffect, useCallback } from 'react';
import { notificationManager, type NotificationPermissionState, type TradingNotification } from '../utils/notifications';

interface NotificationState {
  isEnabled: boolean;
  permission: NotificationPermissionState;
  isInitialized: boolean;
  error: string | null;
  stats: {
    enabled: boolean;
    permission: NotificationPermissionState;
    activeCount: number;
    queuedCount: number;
    soundEnabled: boolean;
  };
}

interface NotificationActions {
  initialize: () => Promise<boolean>;
  sendSignalNotification: (signal: {
    symbol: string;
    direction: string;
    confidence: number;
    entry: number;
    riskReward: number;
  }) => void;
  sendRiskAlert: (alert: {
    type: 'exposure_limit' | 'loss_limit' | 'max_positions' | 'drawdown';
    message: string;
    severity: 'warning' | 'critical';
  }) => void;
  sendExecutionNotification: (execution: {
    symbol: string;
    side: string;
    quantity: number;
    price: number;
    status: 'filled' | 'partial' | 'cancelled' | 'rejected';
  }) => void;
  sendSystemNotification: (message: {
    title: string;
    body: string;
    priority?: 'low' | 'normal' | 'high' | 'critical';
    action?: string;
  }) => void;
  clearAllNotifications: () => void;
  setSoundEnabled: (enabled: boolean) => void;
  refreshStats: () => void;
}

export function useNotifications(): [NotificationState, NotificationActions] {
  const [state, setState] = useState<NotificationState>({
    isEnabled: false,
    permission: { granted: false, denied: false, default: true },
    isInitialized: false,
    error: null,
    stats: {
      enabled: false,
      permission: { granted: false, denied: false, default: true },
      activeCount: 0,
      queuedCount: 0,
      soundEnabled: true
    }
  });

  // Initialize notification manager
  const initialize = useCallback(async (): Promise<boolean> => {
    try {
      setState(prev => ({ ...prev, error: null }));
      
      const success = await notificationManager.initialize();
      const permission = notificationManager.getPermissionStatus();
      const stats = notificationManager.getStats();

      setState(prev => ({
        ...prev,
        isEnabled: success,
        permission,
        isInitialized: true,
        stats
      }));

      if (!success) {
        setState(prev => ({
          ...prev,
          error: 'Failed to initialize notifications. Please check browser permissions.'
        }));
      }

      return success;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      setState(prev => ({
        ...prev,
        error: errorMessage,
        isInitialized: true
      }));
      return false;
    }
  }, []);

  // Refresh stats
  const refreshStats = useCallback(() => {
    const stats = notificationManager.getStats();
    setState(prev => ({ ...prev, stats }));
  }, []);

  // Auto-refresh stats periodically
  useEffect(() => {
    const interval = setInterval(refreshStats, 5000); // Every 5 seconds
    return () => clearInterval(interval);
  }, [refreshStats]);

  // Notification actions
  const sendSignalNotification = useCallback((signal: {
    symbol: string;
    direction: string;
    confidence: number;
    entry: number;
    riskReward: number;
  }) => {
    notificationManager.notifyHighConfidenceSignal(signal);
    refreshStats();
  }, [refreshStats]);

  const sendRiskAlert = useCallback((alert: {
    type: 'exposure_limit' | 'loss_limit' | 'max_positions' | 'drawdown';
    message: string;
    severity: 'warning' | 'critical';
  }) => {
    notificationManager.notifyRiskAlert(alert);
    refreshStats();
  }, [refreshStats]);

  const sendExecutionNotification = useCallback((execution: {
    symbol: string;
    side: string;
    quantity: number;
    price: number;
    status: 'filled' | 'partial' | 'cancelled' | 'rejected';
  }) => {
    notificationManager.notifyOrderExecution(execution);
    refreshStats();
  }, [refreshStats]);

  const sendSystemNotification = useCallback((message: {
    title: string;
    body: string;
    priority?: 'low' | 'normal' | 'high' | 'critical';
    action?: string;
  }) => {
    notificationManager.notifySystem(message);
    refreshStats();
  }, [refreshStats]);

  const clearAllNotifications = useCallback(() => {
    notificationManager.clearAllNotifications();
    refreshStats();
  }, [refreshStats]);

  const setSoundEnabled = useCallback((enabled: boolean) => {
    notificationManager.setSoundEnabled(enabled);
    refreshStats();
  }, [refreshStats]);

  // Auto-initialize on first render (if not already initialized)
  useEffect(() => {
    if (!state.isInitialized) {
      initialize();
    }
  }, [initialize, state.isInitialized]);

  const actions: NotificationActions = {
    initialize,
    sendSignalNotification,
    sendRiskAlert,
    sendExecutionNotification,
    sendSystemNotification,
    clearAllNotifications,
    setSoundEnabled,
    refreshStats
  };

  return [state, actions];
}

// Convenience hook for quick notification sending
export function useQuickNotifications() {
  const [, actions] = useNotifications();

  return {
    notifySignal: actions.sendSignalNotification,
    notifyRisk: actions.sendRiskAlert,
    notifyExecution: actions.sendExecutionNotification,
    notifySystem: actions.sendSystemNotification
  };
}
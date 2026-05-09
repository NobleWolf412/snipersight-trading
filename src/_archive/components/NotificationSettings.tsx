/**
 * Notification Settings Component
 * 
 * Allows users to configure browser notification preferences
 * including permissions, sound settings, and notification types.
 */

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, Bell, BellOff, Volume2, VolumeX, Settings, Shield, TrendingUp, Activity } from 'lucide-react';
import { useNotifications } from '@/hooks/useNotifications';

interface NotificationSettingsProps {
  className?: string;
}

export function NotificationSettings({ className = '' }: NotificationSettingsProps) {
  const [notificationState, notificationActions] = useNotifications();

  const getPermissionBadge = () => {
    if (notificationState.permission.granted) {
      return <Badge variant="default" className="gap-1 bg-green-500 text-white"><Bell size={12} />Enabled</Badge>;
    }
    if (notificationState.permission.denied) {
      return <Badge variant="destructive" className="gap-1"><BellOff size={12} />Denied</Badge>;
    }
    return <Badge variant="secondary" className="gap-1"><AlertCircle size={12} />Not Set</Badge>;
  };

  const handleEnableNotifications = async () => {
    const success = await notificationActions.initialize();
    if (!success) {
      // Show instructions to user for manual permission grant
      console.log('Please manually enable notifications in browser settings');
    }
  };

  const handleTestNotification = () => {
    if (!notificationState.isEnabled) {
      return;
    }

    // Send a test signal notification
    notificationActions.sendSignalNotification({
      symbol: 'BTCUSDT',
      direction: 'LONG',
      confidence: 85.7,
      entry: 43250.50,
      riskReward: 2.8
    });
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Main Settings Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell size={20} />
            Browser Notifications
          </CardTitle>
          <CardDescription>
            Get real-time alerts for trading signals, risk events, and order executions
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Permission Status */}
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="font-medium">Permission Status</div>
              <div className="text-sm text-muted-foreground">
                Browser permission for showing notifications
              </div>
            </div>
            <div className="flex items-center gap-3">
              {getPermissionBadge()}
              {!notificationState.permission.granted && (
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={handleEnableNotifications}
                  disabled={notificationState.permission.denied}
                >
                  {notificationState.permission.denied ? 'Blocked' : 'Enable'}
                </Button>
              )}
            </div>
          </div>

          {/* Error Display */}
          {notificationState.error && (
            <div className="p-3 border border-destructive/20 bg-destructive/5 rounded-md">
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertCircle size={16} />
                {notificationState.error}
              </div>
            </div>
          )}

          {/* Sound Settings */}
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="font-medium">Sound Alerts</div>
              <div className="text-sm text-muted-foreground">
                Play sounds for high-priority notifications
              </div>
            </div>
            <div className="flex items-center gap-2">
              {notificationState.stats.soundEnabled ? (
                <Volume2 size={16} className="text-muted-foreground" />
              ) : (
                <VolumeX size={16} className="text-muted-foreground" />
              )}
              <Switch
                checked={notificationState.stats.soundEnabled}
                onCheckedChange={notificationActions.setSoundEnabled}
                disabled={!notificationState.isEnabled}
              />
            </div>
          </div>

          {/* Test Notification */}
          {notificationState.isEnabled && (
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <div className="font-medium">Test Notifications</div>
                <div className="text-sm text-muted-foreground">
                  Send a sample notification to verify settings
                </div>
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleTestNotification}
              >
                Send Test
              </Button>
            </div>
          )}

          {/* Stats */}
          {notificationState.isEnabled && (
            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
              <div className="text-center">
                <div className="text-lg font-semibold">{notificationState.stats.activeCount}</div>
                <div className="text-xs text-muted-foreground">Active</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold">{notificationState.stats.queuedCount}</div>
                <div className="text-xs text-muted-foreground">Queued</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notification Types Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings size={20} />
            Notification Types
          </CardTitle>
          <CardDescription>
            Configure which types of events trigger notifications
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Trading Signals */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-md bg-blue-500/10">
                <TrendingUp size={16} className="text-blue-500" />
              </div>
              <div className="space-y-1">
                <div className="font-medium">High-Confidence Signals</div>
                <div className="text-sm text-muted-foreground">
                  Trading opportunities with 80%+ confidence
                </div>
              </div>
            </div>
            <Switch defaultChecked />
          </div>

          {/* Risk Alerts */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-md bg-red-500/10">
                <Shield size={16} className="text-red-500" />
              </div>
              <div className="space-y-1">
                <div className="font-medium">Risk Alerts</div>
                <div className="text-sm text-muted-foreground">
                  Exposure limits, loss alerts, and risk violations
                </div>
              </div>
            </div>
            <Switch defaultChecked />
          </div>

          {/* Order Executions */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-md bg-green-500/10">
                <Activity size={16} className="text-green-500" />
              </div>
              <div className="space-y-1">
                <div className="font-medium">Order Executions</div>
                <div className="text-sm text-muted-foreground">
                  Order fills, cancellations, and rejections
                </div>
              </div>
            </div>
            <Switch defaultChecked />
          </div>

          {/* System Notifications */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-md bg-gray-500/10">
                <Bell size={16} className="text-gray-500" />
              </div>
              <div className="space-y-1">
                <div className="font-medium">System Notifications</div>
                <div className="text-sm text-muted-foreground">
                  Connection issues, updates, and system alerts
                </div>
              </div>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>

      {/* Browser Instructions */}
      {notificationState.permission.denied && (
        <Card className="border-amber-200 bg-amber-50">
          <CardHeader>
            <CardTitle className="text-amber-800">Manual Permission Required</CardTitle>
            <CardDescription className="text-amber-700">
              Notifications are currently blocked. To enable them:
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-amber-800">
            <div>1. Click the lock icon in your browser's address bar</div>
            <div>2. Set "Notifications" to "Allow"</div>
            <div>3. Refresh this page</div>
            <div className="pt-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => window.location.reload()}
                className="border-amber-300 text-amber-800 hover:bg-amber-100"
              >
                Refresh Page
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
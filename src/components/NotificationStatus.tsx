/**
 * Notification Status Indicator
 * 
 * Displays notification permission status and unread count
 * in the navigation bar with quick access to settings.
 */

import React, { useState } from 'react';
import { Bell, BellOff, Settings } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationSettings } from '../NotificationSettings';

interface NotificationStatusProps {
  className?: string;
}

export function NotificationStatus({ className = '' }: NotificationStatusProps) {
  const [notificationState, notificationActions] = useNotifications();
  const [showSettings, setShowSettings] = useState(false);

  const getStatusIcon = () => {
    if (!notificationState.isInitialized) {
      return <Bell size={18} className="text-muted-foreground animate-pulse" />;
    }

    if (notificationState.permission.granted && notificationState.isEnabled) {
      return <Bell size={18} className="text-green-500" />;
    }

    if (notificationState.permission.denied) {
      return <BellOff size={18} className="text-red-500" />;
    }

    return <Bell size={18} className="text-yellow-500" />;
  };

  const getStatusText = () => {
    if (!notificationState.isInitialized) {
      return 'Initializing...';
    }

    if (notificationState.permission.granted && notificationState.isEnabled) {
      return 'Notifications Enabled';
    }

    if (notificationState.permission.denied) {
      return 'Notifications Blocked';
    }

    if (notificationState.permission.default) {
      return 'Notifications Not Set';
    }

    return 'Notifications Disabled';
  };

  const getStatusBadge = () => {
    if (!notificationState.isInitialized) return null;

    if (notificationState.permission.granted && notificationState.isEnabled) {
      return notificationState.stats.activeCount > 0 ? (
        <Badge variant="destructive" className="absolute -top-1 -right-1 px-1 py-0 text-xs min-w-[16px] h-4">
          {notificationState.stats.activeCount}
        </Badge>
      ) : null;
    }

    if (notificationState.permission.denied) {
      return (
        <Badge variant="destructive" className="absolute -top-1 -right-1 px-1 py-0 text-xs">
          !
        </Badge>
      );
    }

    if (notificationState.permission.default) {
      return (
        <Badge variant="secondary" className="absolute -top-1 -right-1 px-1 py-0 text-xs">
          ?
        </Badge>
      );
    }

    return null;
  };

  return (
    <div className={`relative ${className}`}>
      <Popover open={showSettings} onOpenChange={setShowSettings}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="relative p-2 hover:bg-accent/50"
            title={getStatusText()}
          >
            {getStatusIcon()}
            {getStatusBadge()}
          </Button>
        </PopoverTrigger>
        <PopoverContent 
          className="w-96 p-0" 
          align="end"
          side="bottom"
        >
          <Card className="border-0 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  {getStatusIcon()}
                  Notifications
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowSettings(false)}
                >
                  ×
                </Button>
              </CardTitle>
              <CardDescription>
                {getStatusText()}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Quick Stats */}
              {notificationState.isEnabled && (
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded bg-muted/50">
                    <div className="text-lg font-semibold">{notificationState.stats.activeCount}</div>
                    <div className="text-xs text-muted-foreground">Active</div>
                  </div>
                  <div className="p-2 rounded bg-muted/50">
                    <div className="text-lg font-semibold">{notificationState.stats.queuedCount}</div>
                    <div className="text-xs text-muted-foreground">Queued</div>
                  </div>
                  <div className="p-2 rounded bg-muted/50">
                    <div className="text-lg font-semibold">
                      {notificationState.stats.soundEnabled ? '🔊' : '🔇'}
                    </div>
                    <div className="text-xs text-muted-foreground">Sound</div>
                  </div>
                </div>
              )}

              {/* Quick Actions */}
              <div className="space-y-2">
                {!notificationState.permission.granted && !notificationState.permission.denied && (
                  <Button 
                    className="w-full"
                    onClick={async () => {
                      await notificationActions.initialize();
                    }}
                  >
                    Enable Notifications
                  </Button>
                )}

                {notificationState.isEnabled && (
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="flex-1"
                      onClick={() => {
                        // Test notification
                        notificationActions.sendSystemNotification({
                          title: '🔔 Test Notification',
                          body: 'Browser notifications are working correctly',
                          priority: 'normal'
                        });
                      }}
                    >
                      Test
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="flex-1"
                      onClick={() => {
                        notificationActions.clearAllNotifications();
                      }}
                    >
                      Clear All
                    </Button>
                  </div>
                )}

                {notificationState.permission.denied && (
                  <div className="text-sm text-muted-foreground text-center p-3 bg-muted/50 rounded">
                    Notifications are blocked. Click the lock icon in your browser's address bar to enable them.
                  </div>
                )}

                {notificationState.error && (
                  <div className="text-sm text-destructive text-center p-3 bg-destructive/10 rounded">
                    {notificationState.error}
                  </div>
                )}
              </div>

              {/* Link to Full Settings */}
              <Button
                variant="ghost"
                className="w-full justify-start"
                onClick={() => {
                  // Navigate to settings page or show full settings modal
                  console.log('Navigate to notification settings');
                  setShowSettings(false);
                }}
              >
                <Settings size={16} className="mr-2" />
                Advanced Settings
              </Button>
            </CardContent>
          </Card>
        </PopoverContent>
      </Popover>
    </div>
  );
}
/**
 * Debug Logger Service
 * 
 * Captures API activity and scan events for display in the ScannerConsole.
 * Uses an event-driven approach so components can subscribe to real-time logs.
 */

export interface DebugLogEntry {
  timestamp: number;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'api';
  source: 'api' | 'scanner' | 'system';
}

type LogListener = (entry: DebugLogEntry) => void;

export enum LogLevel {
  SILENT = 0,
  ERROR = 1,
  WARN = 2,
  INFO = 3,
  DEBUG = 4,
}

class DebugLoggerService {
  private logs: DebugLogEntry[] = [];
  private listeners: Set<LogListener> = new Set();
  private maxLogs = 200;
  private level: LogLevel = (import.meta.env.MODE === 'production') ? LogLevel.WARN : LogLevel.INFO;

  /**
   * Add a log entry and notify all listeners
   */
  log(
    message: string, 
    type: DebugLogEntry['type'] = 'info',
    source: DebugLogEntry['source'] = 'system'
  ): void {
    const neededLevel = ((): LogLevel => {
      if (type === 'error') return LogLevel.ERROR;
      if (type === 'warning') return LogLevel.WARN;
      if (type === 'api') return LogLevel.DEBUG;
      // Treat scanner info/success as Essential so they show at WARN level
      if ((type === 'info' || type === 'success') && source === 'scanner') return LogLevel.WARN;
      if (type === 'info' || type === 'success') return LogLevel.INFO;
      return LogLevel.INFO;
    })();

    if (this.level < neededLevel) return;

    const entry: DebugLogEntry = {
      timestamp: Date.now(),
      message,
      type,
      source
    };
    
    this.logs.push(entry);
    
    // Trim old logs
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }
    
    // Also log to browser console for debugging
    const prefix = `[${source.toUpperCase()}]`;
    switch (type) {
      case 'error':
        console.error(prefix, message);
        break;
      case 'warning':
        console.warn(prefix, message);
        break;
      default:
        console.log(prefix, message);
    }
    
    // Notify listeners
    this.listeners.forEach(listener => listener(entry));
  }

  /**
   * Convenience methods for different log levels
   */
  info(message: string, source: DebugLogEntry['source'] = 'system'): void {
    this.log(message, 'info', source);
  }

  success(message: string, source: DebugLogEntry['source'] = 'system'): void {
    this.log(message, 'success', source);
  }

  warning(message: string, source: DebugLogEntry['source'] = 'system'): void {
    this.log(message, 'warning', source);
  }

  error(message: string, source: DebugLogEntry['source'] = 'system'): void {
    this.log(message, 'error', source);
  }

  api(message: string): void {
    this.log(message, 'api', 'api');
  }

  /**
   * Subscribe to log events
   */
  subscribe(listener: LogListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Get all current logs
   */
  getLogs(): DebugLogEntry[] {
    return [...this.logs];
  }

  /**
   * Clear all logs
   */
  clear(): void {
    this.logs = [];
  }

  setLogLevel(level: LogLevel): void {
    this.level = level;
  }

  getLogLevel(): LogLevel {
    return this.level;
  }
}

// Singleton instance
export const debugLogger = new DebugLoggerService();

// Make it available globally for easy access in browser console
if (typeof window !== 'undefined') {
  (window as any).__debugLogger = debugLogger;
}

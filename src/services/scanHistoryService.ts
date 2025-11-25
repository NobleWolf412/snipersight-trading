/**
 * Scan History Service
 * 
 * Manages persistent storage of scan results in localStorage.
 * Provides a lightweight database for historical scan tracking.
 */

export interface ScanHistoryEntry {
  id: string;
  timestamp: string;
  mode: string;
  profile: string;
  timeframes: string[];
  symbolsScanned: number;
  signalsGenerated: number;
  signalsRejected: number;
  effectiveMinScore: number;
  rejectionBreakdown?: {
    low_confluence: number;
    no_data: number;
    risk_validation: number;
    no_trade_plan: number;
    errors: number;
  };
  results: any[]; // Actual scan results (signals)
}

const STORAGE_KEY = 'scan-history';
const MAX_HISTORY_ENTRIES = 50; // Keep last 50 scans

class ScanHistoryService {
  /**
   * Save a new scan to history
   */
  saveScan(entry: Omit<ScanHistoryEntry, 'id' | 'timestamp'>): ScanHistoryEntry {
    const newEntry: ScanHistoryEntry = {
      ...entry,
      id: `scan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
    };

    const history = this.getAllScans();
    history.unshift(newEntry); // Add to beginning

    // Trim to max entries
    const trimmed = history.slice(0, MAX_HISTORY_ENTRIES);

    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    return newEntry;
  }

  /**
   * Get all scans from history
   */
  getAllScans(): ScanHistoryEntry[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      console.error('Failed to parse scan history:', e);
      return [];
    }
  }

  /**
   * Get scans within a time range
   */
  getScansInRange(startTime: Date, endTime?: Date): ScanHistoryEntry[] {
    const all = this.getAllScans();
    const end = endTime || new Date();

    return all.filter(scan => {
      const scanTime = new Date(scan.timestamp);
      return scanTime >= startTime && scanTime <= end;
    });
  }

  /**
   * Get recent scans (last N hours)
   */
  getRecentScans(hours: number = 24): ScanHistoryEntry[] {
    const startTime = new Date(Date.now() - hours * 60 * 60 * 1000);
    return this.getScansInRange(startTime);
  }

  /**
   * Get scan by ID
   */
  getScanById(id: string): ScanHistoryEntry | null {
    const all = this.getAllScans();
    return all.find(scan => scan.id === id) || null;
  }

  /**
   * Delete scans within time range
   */
  clearScansInRange(startTime: Date, endTime?: Date): number {
    const all = this.getAllScans();
    const end = endTime || new Date();

    const remaining = all.filter(scan => {
      const scanTime = new Date(scan.timestamp);
      return scanTime < startTime || scanTime > end;
    });

    const deletedCount = all.length - remaining.length;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(remaining));
    return deletedCount;
  }

  /**
   * Clear recent scans (last N hours)
   */
  clearRecentScans(hours: number): number {
    const startTime = new Date(Date.now() - hours * 60 * 60 * 1000);
    return this.clearScansInRange(startTime);
  }

  /**
   * Clear all scans
   */
  clearAllScans(): number {
    const all = this.getAllScans();
    const count = all.length;
    localStorage.removeItem(STORAGE_KEY);
    return count;
  }

  /**
   * Get aggregate statistics
   */
  getStatistics(hours?: number): {
    totalScans: number;
    totalSignals: number;
    totalRejections: number;
    avgSignalsPerScan: number;
    avgSuccessRate: number;
    topModes: { mode: string; count: number }[];
  } {
    const scans = hours ? this.getRecentScans(hours) : this.getAllScans();

    if (scans.length === 0) {
      return {
        totalScans: 0,
        totalSignals: 0,
        totalRejections: 0,
        avgSignalsPerScan: 0,
        avgSuccessRate: 0,
        topModes: [],
      };
    }

    const totalSignals = scans.reduce((sum, s) => sum + s.signalsGenerated, 0);
    const totalRejections = scans.reduce((sum, s) => sum + s.signalsRejected, 0);

    // Count modes
    const modeCounts: Record<string, number> = {};
    scans.forEach(s => {
      modeCounts[s.mode] = (modeCounts[s.mode] || 0) + 1;
    });

    const topModes = Object.entries(modeCounts)
      .map(([mode, count]) => ({ mode, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 3);

    const avgSignalsPerScan = totalSignals / scans.length;
    const avgSuccessRate = scans.reduce((sum, s) => {
      const total = s.signalsGenerated + s.signalsRejected;
      return sum + (total > 0 ? (s.signalsGenerated / total) * 100 : 0);
    }, 0) / scans.length;

    return {
      totalScans: scans.length,
      totalSignals,
      totalRejections,
      avgSignalsPerScan: Number(avgSignalsPerScan.toFixed(1)),
      avgSuccessRate: Number(avgSuccessRate.toFixed(1)),
      topModes,
    };
  }
}

// Singleton instance
export const scanHistoryService = new ScanHistoryService();

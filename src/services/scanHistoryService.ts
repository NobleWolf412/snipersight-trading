/**
 * Scan History Service
 * 
 * Manages persistent storage of scan results in localStorage.
 * Provides a lightweight database for historical scan tracking.
 */

// 3a' (Phase 3 follow-up): per-stage rejection sample. The shape mirrors
// the backend orchestrator's failure record dicts loosely — fields vary
// by stage (e.g., confluence rejections include `score`, planner
// rejections include `reason`), so we keep this open-ended and let
// individual chip render paths pick out what they need.
export interface RejectionSampleRecord {
  symbol?: string;
  reason?: string;
  score?: number;
  threshold?: number;
  [key: string]: unknown;
}

// 3a': full per-run rejection bundle persisted alongside results. By
// keeping the raw `by_reason` + `features_breakdown` + `details` shapes
// here we preserve the §11 observability bond — the panel can render
// counts AND click-expand into samples for any past scan from history
// without needing to re-poll the live diagnostics endpoint (which only
// reflects the most-recent orchestrator state, not the run the operator
// clicked into).
export interface ScanRejectionSummary {
  total_rejected: number;
  by_reason: Record<string, number>;
  details?: Record<string, RejectionSampleRecord[]>;
  features_breakdown?: {
    indicator_failures?: { count: number; samples: RejectionSampleRecord[] };
    smc_rejections?: { count: number; samples: RejectionSampleRecord[] };
  };
  direction_stats?: Record<string, unknown>;
  regime?: Record<string, unknown> | null;
}

// 3a': universe snapshot captured at scan completion. Latest-snapshot
// semantics (per briefing acknowledgement) — the cache may have advanced
// between scan completion and panel render, but for the diagnostic loop
// 95% case the alignment is fine. CycleAuditStrip shows the cycle
// timing so a stale snapshot is observable.
export interface UniverseSnapshot {
  // Total candidates the universe selector started with.
  total_candidates: number;
  // Counts per reason — keys: stable_base, non_perp, bucket_excluded,
  // limit_exhausted.
  drops_by_reason: Record<string, number>;
  // Up to ~10 example symbols per reason for click-expand.
  drops_by_reason_samples?: Record<string, string[]>;
  // Snapshot timestamp (epoch seconds) — null if cache cold.
  last_refresh_ts: number | null;
}

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
  // Flexible record type to accommodate backend's dynamic rejection reasons
  rejectionBreakdown?: Record<string, number>;
  // 3a': full per-run rejection bundle — drives the RejectionPanel
  // chips + click-expand details. Optional so older history entries
  // (from before 3a' shipped) still parse cleanly.
  rejectionSummary?: ScanRejectionSummary;
  // 3a': universe snapshot at scan completion. Optional for the same
  // backward-compat reason.
  universeSnapshot?: UniverseSnapshot;
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

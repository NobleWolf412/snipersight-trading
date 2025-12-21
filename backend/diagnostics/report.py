"""
Report Generator for SniperSight Diagnostic Backtest

Generates comprehensive markdown reports from diagnostic logs.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json

from .logger import DiagnosticLogger, Severity


@dataclass
class ModeStats:
    """Statistics for a single mode."""
    mode: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_rr: float = 0.0
    total_pnl_pct: float = 0.0
    issues_found: int = 0
    critical_issues: int = 0
    warnings: int = 0


class ReportGenerator:
    """
    Generates markdown diagnostic reports.
    """
    
    def __init__(self, output_dir: Path, logger: DiagnosticLogger):
        self.output_dir = Path(output_dir)
        self.logger = logger
    
    def generate(
        self,
        mode_stats: Dict[str, ModeStats],
        regime_stats: Dict[str, Dict[str, Any]],
        config: Dict[str, Any],
        start_time: datetime,
        end_time: datetime
    ) -> Path:
        """
        Generate the full diagnostic report.
        
        Returns:
            Path to the generated report
        """
        report_path = self.output_dir / "diagnostic_report.md"
        
        lines = []
        
        # Header
        lines.append("# SniperSight Diagnostic Backtest Report\n")
        lines.append(f"*Generated: {datetime.utcnow().isoformat()}Z*\n")
        
        # Executive Summary
        lines.append("\n## Executive Summary\n")
        lines.append(self._generate_summary(mode_stats, config, start_time, end_time))
        
        # Win Rates by Mode
        lines.append("\n## Win Rates by Mode\n")
        lines.append(self._generate_mode_table(mode_stats))
        
        # Win Rates by Regime
        if regime_stats:
            lines.append("\n## Performance by Market Regime\n")
            lines.append(self._generate_regime_table(regime_stats))
        
        # Issues Found
        stats = self.logger.get_stats()
        lines.append("\n## Issues Found\n")
        lines.append(self._generate_issues_summary(stats))
        
        # Critical Issues Detail
        critical_entries = self.logger.get_entries(severity=Severity.ERROR, limit=50)
        if critical_entries:
            lines.append("\n## Critical Issues (Detail)\n")
            lines.append(self._generate_issues_detail(critical_entries))
        
        # Recommendations
        lines.append("\n## Recommendations\n")
        lines.append(self._generate_recommendations(mode_stats, stats))
        
        # Config Used
        lines.append("\n## Configuration\n")
        lines.append(f"```json\n{json.dumps(config, indent=2)}\n```\n")
        
        # Write report
        with open(report_path, "w") as f:
            f.write("\n".join(lines))
        
        return report_path
    
    def _generate_summary(
        self,
        mode_stats: Dict[str, ModeStats],
        config: Dict[str, Any],
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """Generate executive summary section."""
        total_trades = sum(s.trades for s in mode_stats.values())
        total_wins = sum(s.wins for s in mode_stats.values())
        total_issues = sum(s.issues_found for s in mode_stats.values())
        
        duration = end_time - start_time
        hours = duration.total_seconds() / 3600
        
        overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        lines = [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| **Period** | {config.get('days', 'N/A')} days |",
            f"| **Symbols** | {len(config.get('symbols', []))} |",
            f"| **Modes Tested** | {', '.join(mode_stats.keys())} |",
            f"| **Total Trades** | {total_trades} |",
            f"| **Overall Win Rate** | {overall_wr:.1f}% |",
            f"| **Issues Found** | {total_issues} |",
            f"| **Run Time** | {hours:.1f} hours |",
            ""
        ]
        return "\n".join(lines)
    
    def _generate_mode_table(self, mode_stats: Dict[str, ModeStats]) -> str:
        """Generate mode comparison table."""
        lines = [
            "| Mode | Win Rate | Trades | Wins | Losses | Avg R:R | Issues |",
            "|------|----------|--------|------|--------|---------|--------|"
        ]
        
        for mode, stats in sorted(mode_stats.items()):
            wr_color = "🟢" if stats.win_rate >= 50 else "🔴"
            lines.append(
                f"| **{mode.title()}** | {wr_color} {stats.win_rate:.1f}% | "
                f"{stats.trades} | {stats.wins} | {stats.losses} | "
                f"{stats.avg_rr:.2f} | {stats.issues_found} |"
            )
        
        lines.append("")
        return "\n".join(lines)
    
    def _generate_regime_table(self, regime_stats: Dict[str, Dict[str, Any]]) -> str:
        """Generate regime performance table."""
        lines = [
            "| Regime | Trades | Win Rate | Avg R:R |",
            "|--------|--------|----------|---------|"
        ]
        
        for regime, stats in sorted(regime_stats.items()):
            trades = stats.get("trades", 0)
            wins = stats.get("wins", 0)
            wr = (wins / trades * 100) if trades > 0 else 0
            avg_rr = stats.get("avg_rr", 0)
            
            lines.append(f"| {regime} | {trades} | {wr:.1f}% | {avg_rr:.2f} |")
        
        lines.append("")
        return "\n".join(lines)
    
    def _generate_issues_summary(self, stats: Dict[str, Any]) -> str:
        """Generate issues summary."""
        counts = stats.get("counts", {})
        by_category = stats.get("by_category", {})
        
        lines = [
            f"| Severity | Count |",
            f"|----------|-------|",
            f"| 🚨 Critical | {counts.get('critical', 0)} |",
            f"| 🔴 Error | {counts.get('error', 0)} |",
            f"| ⚠️ Warning | {counts.get('warning', 0)} |",
            f"| ℹ️ Info | {counts.get('info', 0)} |",
            f"| **Total** | {counts.get('total', 0)} |",
            ""
        ]
        
        if by_category:
            lines.append("\n### By Category\n")
            lines.append("| Category | Count |")
            lines.append("|----------|-------|")
            for cat, count in sorted(by_category.items(), key=lambda x: -x[1])[:15]:
                lines.append(f"| `{cat}` | {count} |")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_issues_detail(self, entries: List) -> str:
        """Generate detailed issues list."""
        lines = []
        
        for i, entry in enumerate(entries[:20], 1):
            lines.append(
                f"{i}. **[{entry.probe_id}]** {entry.symbol} ({entry.mode})\n"
                f"   - {entry.message}\n"
                f"   - Context: `{json.dumps(entry.context)[:100]}...`\n"
            )
        
        if len(entries) > 20:
            lines.append(f"\n*... and {len(entries) - 20} more issues in `anomalies.jsonl`*\n")
        
        return "\n".join(lines)
    
    def _generate_recommendations(
        self,
        mode_stats: Dict[str, ModeStats],
        log_stats: Dict[str, Any]
    ) -> str:
        """Generate recommendations based on findings."""
        lines = []
        
        # Find worst performing mode
        worst_mode = min(mode_stats.values(), key=lambda s: s.win_rate) if mode_stats else None
        if worst_mode and worst_mode.win_rate < 45:
            lines.append(
                f"1. **{worst_mode.mode.title()} mode** has the lowest win rate "
                f"({worst_mode.win_rate:.1f}%) - review confluence thresholds and entry criteria.\n"
            )
        
        # Check for common issues
        by_category = log_stats.get("by_category", {})
        
        if by_category.get("plan_stop_entry_error", 0) > 0:
            lines.append(
                "2. **Stop/Entry Logic Errors** detected - CRITICAL fix needed in `planner_service.py`.\n"
            )
        
        if by_category.get("smc_noise", 0) > 5:
            lines.append(
                "3. **SMC Noise** detected in liquidity sweeps - consider tightening timeframe filters.\n"
            )
        
        if by_category.get("regime_unknown", 0) > 3:
            lines.append(
                "4. **Regime Detection** failing - increase candle lookback or check data quality.\n"
            )
        
        if by_category.get("entry_too_wide", 0) > 5:
            lines.append(
                "5. **Entry Zones** too wide - tighten OB-based entry logic.\n"
            )
        
        # Mode-specific issues
        by_mode = log_stats.get("by_mode", {})
        for mode, mode_issues in by_mode.items():
            if mode_issues.get("error", 0) > 10:
                lines.append(
                    f"6. **{mode.title()}** has {mode_issues['error']} errors - prioritize review.\n"
                )
        
        if not lines:
            lines.append("✅ No critical recommendations - scanner performing within expected parameters.\n")
        
        return "\n".join(lines)

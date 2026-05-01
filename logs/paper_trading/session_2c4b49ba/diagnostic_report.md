# SniperSight Diagnostic Backtest Report

*Generated: 2026-04-30T22:34:11.728178Z*


## Executive Summary

| Metric | Value |
|--------|-------|
| **Period** | N/A days |
| **Symbols** | 0 |
| **Modes Tested** | stealth |
| **Total Trades** | 36 |
| **Overall Win Rate** | 58.3% |
| **Issues Found** | 18916 |
| **Run Time** | 24.0 hours |


## Win Rates by Mode

| Mode | Win Rate | Trades | Wins | Losses | Avg R:R | Issues |
|------|----------|--------|------|--------|---------|--------|
| **Stealth** | 🟢 58.3% | 36 | 21 | 15 | 2.26 | 18916 |


## Issues Found

| Severity | Count |
|----------|-------|
| 🚨 Critical | 0 |
| 🔴 Error | 0 |
| ⚠️ Warning | 18880 |
| ℹ️ Info | 36 |
| **Total** | 18916 |


### By Category

| Category | Count |
|----------|-------|
| `signal_filtered` | 9671 |
| `conf_breakdown_mismatch` | 8274 |
| `data_missing` | 884 |
| `plan_rr_low` | 51 |
| `exec_success` | 36 |


## Recommendations

✅ No critical recommendations - scanner performing within expected parameters.


## Configuration

```json
{
  "exchange": "phemex",
  "sniper_mode": "stealth",
  "initial_balance": 10000.0,
  "risk_per_trade": 2.0,
  "max_positions": 10,
  "leverage": 1,
  "duration_hours": 24,
  "scan_interval_minutes": 2,
  "trailing_stop": true,
  "trailing_activation": 2.0,
  "breakeven_after_target": 1,
  "min_confluence": null,
  "confluence_soft_floor": null,
  "sensitivity_preset": "aggressive",
  "symbols": [],
  "exclude_symbols": [],
  "majors": true,
  "altcoins": true,
  "meme_mode": true,
  "slippage_bps": 15.0,
  "fee_rate": 0.001,
  "max_hours_open": 72,
  "max_pending_scans": 2,
  "max_drawdown_pct": 10.0,
  "use_testnet": false,
  "ml_gate_threshold": 0.4,
  "universe_size": 50
}
```

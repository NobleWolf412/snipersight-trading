#!/usr/bin/env python3
"""
Verify timeframe responsibility wiring across all modes.

Prints each mode's allowed TF sets (entry/stop/target/structure/bias) and the
resulting orchestrator config ingestion set after apply_mode(). This validates
mode definitions and orchestrator mapping without requiring a live adapter.
"""
from typing import Any

import sys
from pathlib import Path
# Ensure workspace root on sys.path for 'backend' package imports
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.append(ROOT)

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import MODES, ScannerMode
from backend.engine.orchestrator import Orchestrator

class DummyAdapter:
    """Minimal adapter stub so Orchestrator can be constructed."""
    def __init__(self) -> None:
        self.exchange = None


def summarize_mode(mode: ScannerMode) -> dict[str, Any]:
    # Orchestrator expects config.profile to be a mode NAME (key for get_mode)
    cfg = ScanConfig(profile=mode.name)
    orch = Orchestrator(config=cfg, exchange_adapter=DummyAdapter())
    orch.apply_mode(mode)
    return {
        "mode": mode.name,
        "bias_tfs": list(mode.bias_timeframes),
        "entry_tfs": list(mode.entry_timeframes),
        "structure_tfs": list(mode.structure_timeframes),
        "stop_tfs": list(getattr(mode, "stop_timeframes", ())),
        "target_tfs": list(getattr(mode, "target_timeframes", ())),
        "ingestion_tfs": list(orch.config.timeframes),
        "overrides": getattr(mode, "overrides", {}) or {},
    }


def main() -> None:
    rows = [summarize_mode(m) for m in MODES.values()]
    print("\nTF Responsibility Summary (All Modes)\n" + "-" * 60)
    for r in rows:
        print(f"Mode: {r['mode']}")
        print(f"  Bias TFs:       {r['bias_tfs']}")
        print(f"  Entry TFs:      {r['entry_tfs']}")
        print(f"  Structure TFs:  {r['structure_tfs']}")
        print(f"  Stop TFs:       {r['stop_tfs']}")
        print(f"  Target TFs:     {r['target_tfs']}")
        print(f"  Ingestion TFs:  {r['ingestion_tfs']}")
        if r['overrides']:
            print(f"  Overrides:      {r['overrides']}")
        print("-")


if __name__ == "__main__":
    main()

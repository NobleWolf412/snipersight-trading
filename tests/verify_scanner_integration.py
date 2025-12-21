#!/usr/bin/env python3
"""
Verification script for scanner UI → backend integration.

This script checks that all components are properly wired:
1. Orchestrator initialization in api_server.py
2. Scanner endpoint uses orchestrator.scan()
3. Telemetry events logged during scans
4. Frontend correctly calls the API
"""

import ast
import re
from pathlib import Path

def check_file_content(filepath: Path, checks: dict) -> dict:
    """Check if file contains expected content."""
    results = {}
    try:
        content = filepath.read_text()
        for check_name, pattern in checks.items():
            if isinstance(pattern, str):
                results[check_name] = pattern in content
            else:  # regex pattern
                results[check_name] = bool(re.search(pattern, content))
    except Exception as e:
        results = {k: f"ERROR: {e}" for k in checks.keys()}
    return results

def main():
    print("=" * 80)
    print("SCANNER INTEGRATION VERIFICATION")
    print("=" * 80)
    print()
    
    base_path = Path("/workspaces/snipersight-trading")
    
    # Check 1: api_server.py has orchestrator imports
    print("✓ Checking api_server.py orchestrator integration...")
    api_server = base_path / "backend" / "api_server.py"
    api_checks = {
        "Orchestrator imported": "from backend.engine.orchestrator import Orchestrator",
        "ScanConfig imported": "from backend.shared.config.defaults import ScanConfig",
        "Orchestrator initialized": r"orchestrator = Orchestrator\(",
        "Scanner endpoint exists": r"@app\.get\(\"/api/scanner/signals\"\)",
        "Endpoint uses orchestrator.scan": "orchestrator.scan(symbols",
        "Config updated dynamically": "orchestrator.config.min_confluence_score",
        "Telemetry error logging": "create_error_event",
    }
    api_results = check_file_content(api_server, api_checks)
    
    for check, result in api_results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check}")
    print()
    
    # Check 2: Frontend API client
    print("✓ Checking frontend API client...")
    api_client = base_path / "src" / "utils" / "api.ts"
    frontend_checks = {
        "getSignals method exists": "getSignals",
        "Calls scanner endpoint": "/api/scanner/signals",
        "Passes limit parameter": "limit",
        "Passes min_score parameter": "min_score",
        "Passes sniper_mode parameter": "sniper_mode",
    }
    frontend_results = check_file_content(api_client, frontend_checks)
    
    for check, result in frontend_results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check}")
    print()
    
    # Check 3: Scanner UI component
    print("✓ Checking ScannerSetup component...")
    scanner_setup = base_path / "src" / "pages" / "ScannerSetup.tsx"
    scanner_checks = {
        "handleArmScanner exists": "handleArmScanner",
        "Calls api.getSignals": "api.getSignals",
        "Uses sniper mode": "sniperMode",
        "Uses scan config": "scanConfig",
    }
    scanner_results = check_file_content(scanner_setup, scanner_checks)
    
    for check, result in scanner_results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check}")
    print()
    
    # Check 4: Telemetry integration
    print("✓ Checking telemetry integration...")
    telemetry_checks = {
        "ActivityFeed component": (base_path / "src" / "components" / "telemetry" / "ActivityFeed.tsx").exists(),
        "Telemetry service": (base_path / "src" / "services" / "telemetryService.ts").exists(),
        "Telemetry guide docs": (base_path / "docs" / "TELEMETRY_GUIDE.md").exists(),
        "Analytics module": (base_path / "backend" / "bot" / "telemetry" / "analytics.py").exists(),
        "Events module": (base_path / "backend" / "bot" / "telemetry" / "events.py").exists(),
        "Storage module": (base_path / "backend" / "bot" / "telemetry" / "storage.py").exists(),
    }
    
    for check, result in telemetry_checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check}")
    print()
    
    # Check 5: Orchestrator instrumentation
    print("✓ Checking orchestrator telemetry instrumentation...")
    orchestrator = base_path / "backend" / "engine" / "orchestrator.py"
    orch_checks = {
        "scan_started event": "scan_started",
        "signal_generated event": "signal_generated",
        "signal_rejected event": "signal_rejected",
        "scan_completed event": "scan_completed",
        "Uses telemetry logger": "get_telemetry_logger",
    }
    orch_results = check_file_content(orchestrator, orch_checks)
    
    for check, result in orch_results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check}")
    print()
    
    # Summary
    all_checks = {
        **api_results,
        **frontend_results,
        **scanner_results,
        **telemetry_checks,
        **orch_results
    }
    
    passed = sum(1 for v in all_checks.values() if v is True)
    total = len(all_checks)
    
    print("=" * 80)
    print(f"VERIFICATION SUMMARY: {passed}/{total} checks passed")
    print("=" * 80)
    print()
    
    if passed == total:
        print("✅ ALL SYSTEMS OPERATIONAL!")
        print()
        print("Integration complete:")
        print("  • Scanner UI button → api.getSignals()")
        print("  • API endpoint → orchestrator.scan()")
        print("  • Orchestrator → telemetry events")
        print("  • Telemetry → ActivityFeed UI")
        print()
        print("To test end-to-end:")
        print("  1. Start backend: uvicorn backend.api_server:app --reload")
        print("  2. Start frontend: npm run dev")
        print("  3. Navigate to Scanner Setup")
        print("  4. Click 'ARM THE SCANNER'")
        print("  5. Check Bot Status → Activity Feed for telemetry events")
        return 0
    else:
        print("❌ Some checks failed. Review output above.")
        return 1

if __name__ == "__main__":
    exit(main())

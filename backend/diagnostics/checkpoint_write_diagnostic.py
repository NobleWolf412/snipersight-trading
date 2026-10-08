"""Exercise checkpoint creation, replacement, failed publication and retry offline.

Run: python backend/diagnostics/checkpoint_write_diagnostic.py
Exit 0: all checks pass; exit 1: checkpoint invariant failed; exit 2: diagnostic error.
The service module is parsed, never imported. No credentials, network, or bot
startup are used. This tests replacement semantics, not full crash recovery.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch


def diagnose():
    source_path = Path(__file__).resolve().parents[1] / "bot" / "paper_trading_service.py"
    source_bytes = source_path.read_bytes()
    tree = ast.parse(source_bytes.decode("utf-8"))
    service = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PaperTradingService")
    method = next(n for n in service.body if isinstance(n, ast.FunctionDef) and n.name == "_save_state")
    warnings = []
    namespace = {
        "json": json,
        "datetime": datetime,
        "timezone": timezone,
        "logger": SimpleNamespace(warning=warnings.append),
    }
    # Execute only the inspected method, with an empty-position offline fixture.
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source_path), "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix="snipersight-checkpoint-audit-") as temp:
        folder = Path(temp).resolve()
        assert folder.parent == Path(tempfile.gettempdir()).resolve()
        balance = [100.0]
        fixture = SimpleNamespace(
            _session_log_dir=folder,
            position_manager=None,
            _pending_plans={},
            session_id="offline-audit",
            config=None,
            executor=SimpleNamespace(get_balance=lambda: balance[0]),
            stats=SimpleNamespace(to_dict=lambda: {}),
        )
        namespace["_save_state"](fixture)
        first = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        first_ok = first["balance"] == 100.0 and not warnings
        balance[0] = 90.0
        namespace["_save_state"](fixture)
        second = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        replacement_ok = second["balance"] == 90.0 and not warnings
        temp_path = folder / "state.tmp"
        pending = json.loads(temp_path.read_text(encoding="utf-8")) if temp_path.exists() else None
        write_warnings = list(warnings)
        replacement_consumed_temp = not temp_path.exists()
        previous_checkpoint = (folder / "state.json").read_bytes()
        warnings.clear()
        balance[0] = 80.0
        failure_marker = "CHECKPOINT_DIAGNOSTIC_PUBLICATION_DENIED"
        # Simulate an OS publication failure, independent of rename/replace choice.
        # Patches apply only in this isolated process and are restored before cleanup.
        with (
            patch("os.replace", side_effect=PermissionError(failure_marker)) as replace_call,
            patch("os.rename", side_effect=PermissionError(failure_marker)) as rename_call,
        ):
            namespace["_save_state"](fixture)
        publication_attempts = replace_call.call_count + rename_call.call_count
        failure_preserved_checkpoint = (folder / "state.json").read_bytes() == previous_checkpoint
        failure_logged = len(warnings) == 1 and failure_marker in warnings[0]
        failure_warnings = list(warnings)
        warnings.clear()
        balance[0] = 70.0
        namespace["_save_state"](fixture)
        retry = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        retry_ok = retry["balance"] == 70.0 and not warnings and not temp_path.exists()

        def sanitize(messages):
            return [
                message.replace(str(folder).replace("\\", "\\\\"), "<temporary directory>")
                .replace(str(folder), "<temporary directory>")
                for message in messages
            ]

        checks = {
            "first_write": first_ok,
            "replacement": replacement_ok,
            "replacement_consumed_temp": replacement_consumed_temp,
            "failed_publication_attempted": publication_attempts == 1,
            "failed_publication_preserved_checkpoint": failure_preserved_checkpoint,
            "failed_publication_logged": failure_logged,
            "retry_after_failure": retry_ok,
        }
        result = {
            "result": "PASS" if all(checks.values()) else "FAIL_CHECKPOINT_WRITE",
            "checks": checks,
            "platform": os.name,
            "source": "backend/bot/paper_trading_service.py",
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "method": "PaperTradingService._save_state",
            "method_lines": [method.lineno, method.end_lineno],
            "first_write_ok": first_ok,
            "replacement_ok": replacement_ok,
            "first_balance": first["balance"],
            "expected_second_balance": 90.0,
            "persisted_second_balance": second["balance"],
            "pending_temp_balance": pending["balance"] if pending else None,
            "warnings": sanitize(write_warnings),
            "injected_failure_warnings": sanitize(failure_warnings),
            "retry_warnings": sanitize(warnings),
            "retry_balance": retry["balance"],
            "limitations": "Empty positions/orders; no full recovery, concurrency, or trading-path verification.",
        }
    return result


def main():
    try:
        result = diagnose()
    except Exception as exc:
        print("ERROR: checkpoint diagnostic could not complete")
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}, indent=2))
        return 2
    passed = sum(result["checks"].values())
    print(f"{result['result']}: {passed}/{len(result['checks'])} checkpoint checks passed")
    print(json.dumps(result, indent=2))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

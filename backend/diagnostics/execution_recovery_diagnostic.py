"""Offline process-death diagnostic. Only temporary stores and scripted transports.

Usage: python -B backend/diagnostics/execution_recovery_diagnostic.py
Read-only existing-store inspection: append --inspect PATH (no credentials).
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PHASES = ("before_intent", "after_intent", "after_send", "after_partial", "cancel_intent")


def guard_offline(temp_root):
    for name in list(os.environ):
        if name.startswith(("PHEMEX_", "BINANCE_", "TELEGRAM_", "DISCORD_")):
            del os.environ[name]
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(temp_root)
    os.chdir(temp_root)

    def guard(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name == ".env":
                raise RuntimeError("Credential file access blocked")
            mode, flags = args[1] or "", args[2] or 0
            writing = any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            if writing and path != Path(os.devnull).resolve() and not path.is_relative_to(temp_root):
                raise RuntimeError("Write outside diagnostic fixture blocked")
        if event.startswith("socket.") and event in ("socket.connect", "socket.bind", "socket.getaddrinfo"):
            raise RuntimeError("Diagnostic network access blocked")
        if event.startswith("subprocess.") or event == "os.system":
            raise OSError("Nested subprocess blocked")
    sys.addaudithook(guard)


def fault_child(directory, phase, side):
    directory = Path(directory).resolve()
    guard_offline(directory)
    from types import SimpleNamespace as S
    from backend.bot.executor.execution_journal import ExecutionJournal
    from backend.bot.executor.live_executor import LiveExecutor

    journal = ExecutionJournal(directory / "execution.sqlite3", "offline-fixture")

    def die():
        os._exit(73)  # No finally/destructors/SQLite close: exercise OS lock release.

    def send(**wire):
        if phase == "after_intent":
            die()
        with (directory / "sent.json").open("w", encoding="utf-8") as stream:
            json.dump(wire, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if phase == "after_send":
            die()
        return {"id": "remote", "status": "open", "filled": 0}

    adapter = S(supports_trading=lambda: True, fetch_balance=lambda: {"free": {"USDT": 1000}},
                create_order=send, set_margin_mode=lambda *a, **k: None, set_leverage=lambda *a: None,
                cancel_order=lambda *a: die())
    ex = LiveExecutor(adapter, journal=journal, max_position_size_usd=2000, max_total_exposure_usd=2000)
    ex.set_entry_admission(True)
    if phase == "before_intent":
        journal.submit_intent = lambda *a: die()
    order = ex.place_order("A", side, "LIMIT", 10, price=100)
    if phase == "after_partial":
        ex.apply_ws_fill("remote", order.order_id, "partiallyfilled", 4, 100)
        die()
    if phase == "cancel_intent":
        ex.cancel_order(order.order_id)
    raise AssertionError("Fault injection did not terminate at the requested boundary")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect")
    parser.add_argument("--fault-child", choices=PHASES)
    parser.add_argument("--directory")
    parser.add_argument("--side", choices=("BUY", "SELL"), default="BUY")
    parser.add_argument("--lock-child", action="store_true")
    args = parser.parse_args()
    if args.lock_child:
        directory = Path(args.directory).resolve()
        guard_offline(directory)
        from backend.bot.executor.execution_journal import ExecutionJournal
        owner = ExecutionJournal(directory / "execution.sqlite3", "offline-fixture")
        (directory / "ready").write_text("owned", encoding="utf-8")
        sys.stdin.read(1)
        owner.close()
        return 0
    if args.fault_child:
        if not args.directory:
            parser.error("--directory is required for a fault child")
        fault_child(args.directory, args.fault_child, args.side)
        return 2
    from backend.bot.executor.execution_journal import ExecutionJournal
    if args.inspect:
        result = ExecutionJournal.inspect(Path(args.inspect))
        print(json.dumps(result, indent=2))
        return int(result["recovery_required"])
    results = []
    with tempfile.TemporaryDirectory(prefix="snipersight-lock-") as directory:
        process = subprocess.Popen([sys._base_executable, "-B", str(Path(__file__).resolve()),
                                    "--lock-child", "--directory", directory], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        blocked, released = False, False
        try:
            deadline = time.monotonic() + 10
            while not (Path(directory) / "ready").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            if not (Path(directory) / "ready").exists():
                raise RuntimeError("Lock child did not become ready")
            from backend.bot.executor.execution_journal import JournalError
            try:
                accidental_owner = ExecutionJournal(Path(directory) / "execution.sqlite3", "offline-fixture")
            except JournalError:
                blocked = True
            else:
                accidental_owner.close()
            process.kill()
            process.communicate(timeout=10)
            next_owner = ExecutionJournal(Path(directory) / "execution.sqlite3", "offline-fixture")
            released = not next_owner.was_clean
            next_owner.close()
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
        results.append({"phase": "competing_process_then_forced_death", "passed": blocked and released})
    for side in ("BUY", "SELL"):
        for phase in PHASES:
            with tempfile.TemporaryDirectory(prefix="snipersight-crash-") as directory:
                process = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                                          "--fault-child", phase, "--directory", directory, "--side", side],
                                         capture_output=True, timeout=30)
                path = Path(directory) / "execution.sqlite3"
                if process.returncode != 73:
                    results.append({"phase": phase, "side": side, "passed": False,
                                    "returncode": process.returncode,
                                    "error": process.stderr.decode(errors="replace")[-2000:]})
                    continue
                journal = ExecutionJournal(path, "offline-fixture")
                try:
                    rows = journal.records()
                    passed = process.returncode == 73 and not journal.was_clean and len(rows) == (phase != "before_intent")
                    if rows:
                        intent, state = rows[0]
                        passed &= intent["side"] == side
                        passed &= state["filled_quantity"] == (4 if phase == "after_partial" else 0)
                        passed &= state["cancel_requested"] == (phase == "cancel_intent")
                    results.append({"phase": phase, "side": side, "passed": bool(passed)})
                finally:
                    journal.close()
    print(json.dumps({"passed": sum(r["passed"] for r in results), "total": len(results),
                      "scope": "local process death and durable identity; scripted transport, no exchange",
                      "results": results}, indent=2))
    return int(not all(r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())

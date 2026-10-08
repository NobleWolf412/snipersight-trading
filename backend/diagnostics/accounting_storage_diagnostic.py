"""FV1 process-crash probes; disposable journals and scripted facts only.

python -B backend/diagnostics/accounting_storage_diagnostic.py --legacy-journal PATH
PATH optionally selects the actual pre-FV1 source backup for compatibility proof.
No credentials, exchange calls, production-store access or runtime activation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def guard(directory, allow_children):
    for key in list(os.environ):
        if key.startswith(("PHEMEX_", "BINANCE_", "TELEGRAM_", "DISCORD_")):
            del os.environ[key]
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    sys.dont_write_bytecode = True
    os.chdir(directory)
    def audit(event, args):
        if event in ("open", "sqlite3.connect") and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0])
            # SQLite URIs generated from fixture paths only.
            if name.startswith("file:"):
                from urllib.parse import unquote, urlsplit
                name = unquote(urlsplit(name).path)
                if os.name == "nt" and name.startswith("/"):
                    name = name[1:]
            path = Path(name).resolve()
            if path.name == ".env":
                raise RuntimeError("Credentials blocked")
            mode = (args[1] or "") if event == "open" else "w"
            flags = (args[2] or 0) if event == "open" else 0
            write = any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            if write and not path.is_relative_to(directory):
                raise RuntimeError("Write outside fixture blocked")
        if event.startswith("socket.") or event == "os.system":
            raise RuntimeError("Network/shell blocked")
        if event == "subprocess.Popen":
            executable, command = args[:2]
            # subprocess's Windows audit argument is a command-line string.
            if not allow_children or executable != sys.executable or str(Path(__file__).resolve()) not in str(command):
                raise RuntimeError("Unapproved child blocked")
    sys.addaudithook(audit)


def seed(path):
    from backend.bot.executor.execution_journal import ExecutionJournal
    j = ExecutionJournal(path, "fixture")
    now = datetime.now(timezone.utc).isoformat()
    intent = dict(order_id="order", symbol="BTC/USDT:USDT", side="BUY", order_type="LIMIT", quantity=10,
        price=100, stop_price=None, purpose="entry", reduce_only=False, owner="fixture", generation="fixture",
        wire=dict(symbol="BTC/USDT:USDT", side="buy", amount=10, params={"clientOrderId": "order"}))
    state = dict(status="OPEN", filled_quantity=0, average_fill_price=0, exchange_id="remote", unknown_reason=None,
                 cancel_requested=False, rejection_reason=None, created_at=now, updated_at=now)
    j.submit_intent(intent, state)
    j.close()


def worker(path, stage):
    from decimal import Decimal
    from backend.bot.executor.execution_journal import ExecutionJournal, JournalError, upgrade_accounting_schema
    from backend.bot.executor.accounting_models import ObservationContext, ExecutionFact, Fee
    if stage == "owner_exclusion":
        try:
            upgrade_accounting_schema(path, "fixture", environment="testnet")
        except JournalError:
            return 77
        return 1
    original = sqlite3.connect
    class CrashConnection:
        def __init__(self, connection): self.connection = connection
        def __getattr__(self, name): return getattr(self.connection, name)
        def execute(self, sql, *args):
            result = self.connection.execute(sql, *args)
            triggers = {"migration_after_ddl": "CREATE TABLE financial_orders",
                        "record_after_event": "INSERT INTO events",
                        "record_after_projection": "INSERT INTO financial_orders",
                        "record_after_fact": "INSERT INTO execution_facts"}
            if stage in triggers and triggers[stage] in sql:
                os._exit(77)
            return result
        def commit(self):
            if stage.endswith("before_commit"): os._exit(77)
            self.connection.commit()
            if stage.endswith("after_commit"): os._exit(77)
    if stage.startswith("migration"):
        def connect(*args, **kwargs):
            conn = original(*args, **kwargs)
            return CrashConnection(conn) if "mode=rw" in str(args[0]) else conn
        sqlite3.connect = connect
        upgrade_accounting_schema(path, "fixture", environment="testnet")
    else:
        j = ExecutionJournal(path, "fixture")
        j._connection = CrashConnection(j._connection)
        ctx = ObservationContext("testnet", "fixture", "fixture", "crash", datetime.now(timezone.utc).isoformat(), 1.0, 2.0)
        j.record_accounting(ExecutionFact(ctx, "BTC/USDT:USDT", "BUY", "e1", "order", "remote",
                           Decimal(10), Decimal(1060), (Fee("USDT", Decimal("0.2"), "raw"),), cost_provenance="raw"))
    return 1  # The requested interruption must have happened.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=2)
    parser.add_argument("--legacy-journal")
    args = parser.parse_args()
    if args.worker:
        path, stage = Path(args.worker[0]).resolve(), args.worker[1]
        guard(path.parent, False)
        return worker(path, stage)
    directory = Path(tempfile.mkdtemp(prefix="snipersight-fv1-crash-")).resolve()
    guard(directory, True)
    from backend.bot.executor.execution_journal import ExecutionJournal, upgrade_accounting_schema
    results = []
    stages = ["migration_after_ddl", "migration_before_commit", "migration_after_commit",
              "record_after_event", "record_after_projection", "record_after_fact", "record_before_commit", "record_after_commit"]
    try:
        for stage in stages:
            path = directory / (stage + ".sqlite3")
            seed(path)
            marker = path.with_suffix(".initialized").read_bytes()
            if stage.startswith("record"):
                upgrade_accounting_schema(path, "fixture", environment="testnet")
            child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(path), stage],
                                   executable=sys.executable, capture_output=True, text=True, timeout=30)
            if child.returncode != 77:
                raise RuntimeError(f"Crash worker {stage}: {child.returncode} {child.stderr}")
            j = ExecutionJournal(path, "fixture")
            try:
                expected_version = 2 if stage.startswith("record") or stage.endswith("after_commit") else 1
                assert j.schema_version == expected_version
                assert path.with_suffix(".initialized").read_bytes() == marker
                assert j.records()[0][1]["filled_quantity"] == 0
                filled = j.financial_state("order").filled_quantity if expected_version == 2 else 0
                assert filled == (10 if stage == "record_after_commit" else 0)
                if stage == "record_after_commit":
                    assert j.financial_state("order").financially_complete
                results.append({"case": stage, "holds": True, "schema": j.schema_version, "filled": str(filled)})
            finally:
                j.close()
        path = directory / "ownership.sqlite3"
        seed(path)
        j = ExecutionJournal(path, "fixture")
        try:
            child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(path), "owner_exclusion"],
                                   executable=sys.executable, capture_output=True, text=True, timeout=30)
            assert child.returncode == 77, child.stderr
            results.append({"case": "cross_process_owner_exclusion", "holds": True})
        finally:
            j.close()
        if args.legacy_journal:
            legacy = Path(args.legacy_journal).resolve()
            spec = importlib.util.spec_from_file_location("fv1_original_journal", legacy)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            assert "error" not in module.ExecutionJournal.inspect(path)
            upgrade_accounting_schema(path, "fixture", environment="testnet")
            assert "error" in module.ExecutionJournal.inspect(path)
            results.append({"case": "actual_pre_FV1_reader_rejects_v2", "holds": True,
                            "source_sha256": hashlib.sha256(legacy.read_bytes()).hexdigest()})
        report = {"cases": len(results), "all_hold": True, "results": results, "artifact_directory": str(directory)}
        status = 0
    except Exception:
        import traceback
        report = {"harness_error": traceback.format_exc(), "results": results, "artifact_directory": str(directory)}
        status = 2
    report["exit_code"] = status
    (directory / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

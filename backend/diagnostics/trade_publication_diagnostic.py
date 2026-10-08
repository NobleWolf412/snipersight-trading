"""Offline crash/locking/profile proof for completed-trade JSONL publication.

Only disposable files are used; no app bootstrap, credentials or exchange calls.
"""
import argparse
import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def guard(directory, allow_children=False):
    directory = directory.resolve()
    allowed_commands = set()
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name == '.env':
                raise RuntimeError('Credential read blocked')
            mode, flags = args[1] or '', args[2] or 0
            if (any(c in mode for c in 'wax+') or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)) and not path.is_relative_to(directory):
                raise RuntimeError('Write outside diagnostic directory blocked')
        if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo', 'os.system'):
            raise RuntimeError('External operation blocked')
        if event == 'subprocess.Popen':
            command = args[1]
            key = subprocess.list2cmdline(command) if isinstance(command, (list, tuple)) else command
            if not allow_children or key not in allowed_commands:
                raise RuntimeError('Unexpected child process blocked')
    sys.addaudithook(audit)
    return allowed_commands


def worker(directory, stage):
    guard(directory)
    from backend.bot.trade_journal import TradeJournalService
    path = directory / 'trades.jsonl'
    original = os.replace
    def interrupt(source, destination):
        if stage == 'before_replace':
            os._exit(17)
        original(source, destination)
        os._exit(17)
    if stage in ('before_replace', 'after_replace'):
        os.replace = interrupt
    try:
        TradeJournalService(path).upsert({'trade_id': 'next', 'pnl': 2}, 'fixture')
    except OSError as exc:
        if stage == 'writer_busy' and 'WRITER_BUSY' in str(exc):
            return 0
        raise
    return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=('before_replace', 'after_replace', 'writer_busy'))
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    if args.worker:
        if not args.directory or not args.directory.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ValueError('Worker requires a disposable temp directory')
        return worker(args.directory, args.worker)
    for name in list(os.environ):
        if name.startswith(('PHEMEX_', 'BINANCE_', 'TELEGRAM_', 'DISCORD_')):
            del os.environ[name]
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    directory = Path(tempfile.mkdtemp(prefix='snipersight-trade-publication-'))
    allowed_commands = guard(directory, allow_children=True)
    from backend.bot.trade_journal import TradeJournalService
    results = []
    for stage in ('before_replace', 'after_replace', 'writer_busy'):
        fixture = directory / stage
        fixture.mkdir()
        path = fixture / 'trades.jsonl'
        journal = TradeJournalService(path)
        journal.upsert({'trade_id': 'old', 'pnl': 1}, 'fixture')
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker', stage, '--directory', str(fixture)]
        allowed_commands.add(subprocess.list2cmdline(command))
        if stage == 'writer_busy':
            with journal._write_guard():
                child = subprocess.run(command, capture_output=True, text=True, timeout=20)
        else:
            child = subprocess.run(command, capture_output=True, text=True, timeout=20)
        rows = journal.query()
        expected = 2 if stage == 'after_replace' else 1
        retry = journal.upsert({'trade_id': 'next', 'pnl': 2}, 'fixture')
        passed = (child.returncode == (0 if stage == 'writer_busy' else 17)
                  and len(rows) == expected and len(journal.query()) == 2
                  and retry == (stage != 'after_replace'))
        results.append(dict(stage=stage, passed=passed, exit_code=child.returncode,
                            rows_before_retry=len(rows), retry_appended=retry, stderr=child.stderr))
    profile = directory / 'profile.jsonl'
    source = ast.parse((ROOT / 'backend/bot/paper_trading_service.py').read_text(encoding='utf8'))
    definitions = [n for n in source.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                   and n.name in ('CompletedTrade', '_entry_realized_rr')]
    namespace = dict(globals())
    exec(compile(ast.Module(body=definitions, type_ignores=[]), '<actual-trade-serializer>', 'exec'), namespace)
    stamp = datetime(2026, 10, 8, tzinfo=timezone.utc)
    template = namespace['CompletedTrade']('fixture', 'BTC/USDT:USDT', 'LONG', 100, 105, 10,
        stamp, stamp, 50, 5, 'target', target_levels=[105, 110, 115], stop_loss_level=95,
        entry_key_levels={key: {'price': 99, 'swept': False} for key in ('pwh','pwl','pdh','pdl')}).to_dict()
    profile.write_text(''.join(json.dumps(dict(template, trade_id=str(i)))+'\n' for i in range(10000)), encoding='utf8')
    journal = TradeJournalService(profile)
    started = time.perf_counter()
    journal.upsert({'trade_id': 'new', 'pnl': 2}, 'fixture')
    elapsed = (time.perf_counter()-started)*1000
    report = dict(passed=all(r['passed'] for r in results), results=results,
                  profile=dict(existing_rows=10000, row_basis='actual CompletedTrade serializer with synthetic inputs',
                               append_ms=elapsed, bytes=profile.stat().st_size),
                  artifact_directory=str(directory),
                  limits=['OS-process interruption, not hardware power-loss simulation.',
                          'Windows atomic replacement + file fsync tested; POSIX directory fsync not exercised here.'])
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

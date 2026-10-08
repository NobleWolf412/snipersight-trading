"""Read-only persistence inventory; writer fingerprints are not JSON schemas."""
from __future__ import annotations
import ast
from contextlib import closing
import hashlib
from pathlib import Path
import re
import sqlite3


WRITERS = (
    ('backend/bot/paper_trading_service.py', 'CompletedTrade.to_dict'),
    ('backend/bot/paper_trading_service.py', 'CompletedTrade.apply_execution_report'),
    ('backend/bot/trade_journal.py', 'TradeJournalService._classified'),
    ('backend/bot/exit_classification.py', 'enrich'),
    ('backend/bot/executor/execution_reports.py', 'financial_fields'),
    ('backend/bot/executor/execution_reports.py', 'ExecutionReportPublisher.capture'),
    ('backend/bot/executor/execution_reports.py', 'ExecutionReportPublisher._publish'),
    ('backend/bot/executor/execution_reports.py', 'ExecutionReportPublisher.recover'),
    ('backend/bot/executor/execution_outcomes.py', 'ExecutionOutcome.to_dict'),
    ('backend/bot/paper_trading_service.py', 'PaperTradingService._log_signal'),
    ('backend/bot/live_trading_service.py', 'LiveTradingService._log_signal'),
)


def sqlite_tables(source: str):
    """Inspect literal table declarations, including nested constraints and types.

    Only a single CREATE TABLE statement is executed per fresh in-memory DB.
    No application modules or storage files are imported/opened.
    """
    tree = ast.parse(source)
    tables, unresolved = [], []
    inspected = set()
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)
                  and isinstance(node.body[0].value.value, str)}
    calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n:n.lineno)
    for call in calls:
        if not isinstance(call.func, ast.Attribute) or call.func.attr not in ('execute', 'executescript') or not call.args:
            continue
        value = call.args[0]
        inspected.update(id(node) for node in ast.walk(value))
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            if any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and re.search(r'CREATE\s+(?:VIRTUAL\s+)?TABLE', n.value, re.I) for n in ast.walk(value)):
                unresolved.append('dynamic CREATE TABLE expression')
            continue
        sql = value.value.strip()
        if not re.match(r'CREATE\s+TABLE\b', sql, re.I):
            if re.search(r'CREATE\s+(?:VIRTUAL\s+)?TABLE', sql, re.I):
                unresolved.append('nonliteral or multi-statement table initialization')
            continue
        try:
            with closing(sqlite3.connect(':memory:')) as db:
                db.execute(sql)
                rows = db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                if len(rows) != 1:
                    raise ValueError('Expected one table declaration')
                name, declaration = rows[0]
                columns = db.execute('SELECT cid,name,type,"notnull",dflt_value,pk FROM pragma_table_xinfo(?)', (name,)).fetchall()
                tables.append(dict(table=name, columns=sorted(row[1] for row in columns),
                    column_contracts=[dict(name=r[1], type=r[2], not_null=bool(r[3]), default=r[4], primary_key=r[5]) for r in columns],
                    declaration=declaration))
        except (sqlite3.Error, ValueError) as exc:
            unresolved.append('CREATE TABLE cannot be inspected: ' + str(exc))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in inspected and id(node) not in docstrings
                and re.search(r'CREATE\s+(?:VIRTUAL\s+)?TABLE', node.value, re.I)):
            unresolved.append(f'uninspected CREATE TABLE expression at line {node.lineno}')
    return sorted(tables, key=lambda row:row['table']), sorted(set(unresolved))


def writer_contract(source: str, symbol: str):
    """Fingerprint the implementation without pretending dynamic keys are known."""
    node = ast.parse(source)
    for part in symbol.split('.'):
        matches = [n for n in node.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == part]
        if len(matches) != 1:
            raise ValueError('Writer symbol missing or ambiguous: ' + symbol)
        node = matches[0]
    key_hints = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Dict):
            key_hints.update(key.value for key in child.keys if isinstance(key, ast.Constant) and isinstance(key.value, str))
        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == 'update':
            key_hints.update(keyword.arg for keyword in child.keywords if keyword.arg)
    canonical = ast.dump(node, include_attributes=False)
    return dict(symbol=symbol, implementation_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
                literal_key_hints=sorted(key_hints), evidence='writer implementation; hints include nested/conditional keys, not a complete JSON schema')


def capture_storage(root: Path, writers=WRITERS):
    tables, writer_rows, unresolved = [], [], []
    for path in sorted((root/'backend').rglob('*.py')):
        relative = path.relative_to(root)
        if any(part in ('venv', '.venv', '__pycache__', 'tests', 'diagnostics') for part in relative.parts):
            continue
        name = relative.as_posix()
        try:
            source = path.read_text(encoding='utf-8')
            if not re.search(r'CREATE\s+(?:VIRTUAL\s+)?TABLE', source, re.I):
                continue
            found, issues = sqlite_tables(source)
            tables.extend(dict(row, source=name) for row in found)
            unresolved.extend(dict(source=name, reason=issue) for issue in issues)
        except (OSError, UnicodeError, SyntaxError) as exc:
            unresolved.append(dict(source=name, reason=str(exc)))
    for filename, symbol in writers:
        try:
            contract = writer_contract((root/filename).read_text(encoding='utf-8'), symbol)
            writer_rows.append(dict(contract, source=filename))
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            unresolved.append(dict(source=filename, reason=str(exc)))
    return dict(version=2, scope='production literal SQLite declarations and selected JSONL writer implementations',
                sqlite_tables=sorted(tables, key=lambda row:(row['source'],row['table'])),
                jsonl_writers=writer_rows, table_count=len(tables), writer_count=len(writer_rows),
                unresolved=unresolved,
                limitations=['Conditional declarations are inventoried, not proof that a branch runs.',
                             'Known CREATE TABLE expressions outside literal execute calls are unresolved; assembled keywords/external SQL require separate inspection.',
                             'Writer fingerprints detect changes; they do not validate runtime payloads or all dynamically added keys.',
                             'Historical JSONL files are never read or changed.'])

"""Read-only evidence inventory; no strategy replay or performance inference.

Reads the complete local trade journal and three most recently modified session
directories per service. Session mtimes are a sampling rule, not event dates.
Only whitelisted configuration values and case fields are emitted. SQLite opens
in read-only mode; this module never imports the app or an exchange adapter.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sqlite3


def load_records(path: Path):
    raw = path.read_bytes()
    rows, invalid = [], []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            def invalid_constant(value):
                raise ValueError(f'Nonfinite JSON constant: {value}')
            record = json.loads(line.decode('utf-8'), parse_constant=invalid_constant)
            if not isinstance(record, dict):
                raise ValueError('record is not an object')
            rows.append((number, record))
        except (UnicodeDecodeError, ValueError) as error:
            invalid.append({'line': number, 'error_type': type(error).__name__})
    return rows, {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                  'valid_records': len(rows), 'invalid_records': invalid}


def finite_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def evidence_fields(rows):
    """Key presence is evidence availability, never proof of payload completeness."""
    names = {
        'revision': {'git_commit', 'commit_sha', 'code_revision', 'revision'},
        'frozen_prices': {'ohlcv', 'candles', 'frozen_inputs'},
        'config_identity': {'config_hash', 'config_revision', 'config_snapshot'},
        'execution_identity': {'entry_order_id', 'exit_order_ids', 'execution_ids'},
        'actual_fees': {'actual_fees', 'fees_paid', 'execution_fees'},
    }
    counts = Counter()
    def keys(record):
        found = set()
        if isinstance(record, dict):
            for key, value in record.items():
                if value is not None:
                    found.add(key)
                found.update(keys(value))
        elif isinstance(record, list):
            for value in record:
                found.update(keys(value))
        return found
    for _, row in rows:
        present = keys(row)
        for label, candidates in names.items():
            if present & candidates:
                counts[label] += 1
    return {label: counts[label] for label in names}


def brief(number, row, fields):
    return {'line': number, **{key: row.get(key) for key in fields}}


def inspect_history(root: Path, *, sessions=3, telemetry_runs=3):
    journal = root/'backend/cache/trade_journal.jsonl'
    rows, source = load_records(journal)
    ids = Counter(row.get('trade_id') for _, row in rows if row.get('trade_id'))
    outcomes = Counter()
    cases = {}
    for number, row in rows:
        pnl = finite_number(row.get('pnl'))
        label = 'unknown' if pnl is None else ('reported_positive' if pnl > 0 else 'reported_negative' if pnl < 0 else 'reported_zero')
        outcomes[label] += 1
        cases.setdefault(label, brief(number, row, ['trade_id','session_id','symbol','direction','entry_time','exit_time','pnl','exit_reason']))
    source.update(path=str(journal.relative_to(root)), outcomes=dict(outcomes),
                  duplicate_trade_ids={str(k):v for k,v in ids.items() if v > 1},
                  records_missing_trade_id=sum(not row.get('trade_id') for _,row in rows),
                  evidence_key_presence=evidence_fields(rows), sample_cases=cases,
                  session_count=len({r.get('session_id') for _,r in rows}),
                  recorded_execution_modes=dict(Counter(str(r.get('execution_mode')) for _,r in rows)))
    report={'scope':'Saved evidence only; reported outcomes are not verified actual-fee P&L or strategy edge.',
            'journal':source, 'session_sample':[],
            'limitations':['Sampling by directory mtime is not representative sampling.',
                           'Key-presence checks do not certify frozen payload completeness.',
                           'No current candles, market inputs or configuration substituted for missing historical evidence.']}
    safe_config = {'sniper_mode','min_confluence','leverage','risk_per_trade','use_testnet',
                   'execution_mode','macro_overlay_enabled','sensitivity_preset','rr_floor_at_entry'}
    for kind in ('paper_trading','live_trading'):
        base=root/'logs'/kind
        directories=sorted(base.glob('session_*'),key=lambda p:p.stat().st_mtime_ns,reverse=True)
        for directory in directories[:sessions]:
            item={'kind':kind,'session':directory.name,'selection':'directory_mtime_desc', 'files':{}}
            for name in ('signals.jsonl','trades.jsonl','phemex_fills.jsonl'):
                path=directory/name
                if not path.exists():
                    continue
                records, info=load_records(path)
                info['evidence_key_presence']=evidence_fields(records)
                if name=='signals.jsonl':
                    info['results']=dict(Counter(str(r.get('result')) for _,r in records))
                    info['reason_types']=dict(Counter(str(r.get('reason_type')) for _,r in records))
                    info['missing_run_id']=sum(not r.get('run_id') for _,r in records)
                    info['zero_score_long_filtered']=sum(r.get('result')=='filtered' and r.get('direction')=='LONG' and r.get('confluence')==0 for _,r in records)
                    examples={}
                    for number, row in records:
                        examples.setdefault(str(row.get('result')),brief(number,row,
                            ['symbol','direction','timestamp','result','reason_type','scan_number','confluence']))
                    info['first_case_per_result']=examples
                item['files'][name]=info
            for name in ('config.json','session_info.json','state.json'):
                path=directory/name
                if path.exists():
                    raw=path.read_bytes(); document=json.loads(raw.decode('utf-8'))
                    config=document.get('config',document)
                    item['config_source']={'path':name,'sha256':hashlib.sha256(raw).hexdigest(),
                                           'selected_values':{k:config[k] for k in safe_config if k in config},
                                           'evidence_key_presence':evidence_fields([(1,document)])}
                    break
            report['session_sample'].append(item)
    if telemetry_runs:
        from backend.diagnostics.rejection_coverage_audit import _audit_one_cycle
        db=root/'backend/cache/telemetry.db'
        with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as connection:
            connection.row_factory=sqlite3.Row
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            completed=connection.execute("SELECT id,run_id,timestamp,data_json FROM telemetry_events WHERE event_type='scan_completed' ORDER BY id DESC LIMIT ?",(telemetry_runs,)).fetchall()
            report['telemetry_sample']={'path':str(db.relative_to(root)), 'database_bytes':db.stat().st_size,
                                        'selection':'latest inserted scan_completed IDs; read-only transaction', 'cycles':[]}
            for row in completed:
                payload=json.loads(row['data_json'] or '{}')
                audit=_audit_one_cycle(connection,row['run_id'],row['timestamp'],payload)
                info=asdict(audit);info['completed_event_id']=row['id'];info['coverage_gap']=audit.coverage_gap
                info['start_events']=connection.execute("SELECT COUNT(*) FROM telemetry_events WHERE event_type='scan_started' AND run_id=?",(row['run_id'],)).fetchone()[0]
                report['telemetry_sample']['cycles'].append(info)
            connection.rollback()
        report['limitations'].append('Existing coverage helper checks counts/symbol coverage; it does not prove exactly-once decisions or causal replay.')
    assert hashlib.sha256(journal.read_bytes()).hexdigest()==source['sha256'], 'Journal changed during read-only audit'
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--sessions',type=int,default=3)
    parser.add_argument('--telemetry-runs',type=int,default=3)
    args=parser.parse_args()
    if args.sessions < 0 or args.telemetry_runs < 0:
        parser.error('sample counts must be nonnegative')
    print(json.dumps(inspect_history(args.root,sessions=args.sessions,telemetry_runs=args.telemetry_runs),indent=2,allow_nan=False))


if __name__=='__main__':
    main()

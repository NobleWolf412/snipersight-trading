import json

import pytest

from backend.diagnostics.historical_evidence_audit import finite_number, inspect_history, load_records


def test_reader_reports_invalid_evidence_without_silently_dropping_lines(tmp_path):
    path=tmp_path/'history.jsonl'
    payload=b'{"trade_id":"ok"}\nnot-json\n\xff\nnull\n{"pnl":NaN}\n'
    path.write_bytes(payload)
    rows,source=load_records(path)
    assert rows==[(1,{'trade_id':'ok'})]
    assert [r['line'] for r in source['invalid_records']]==[2,3,4,5]
    assert path.read_bytes()==payload


@pytest.mark.parametrize('value',[None,True,False,float('nan'),float('inf'),'unknown'])
def test_missing_invalid_outcome_is_not_a_zero_loss(value):
    assert finite_number(value) is None


def test_history_inventory_keeps_unknown_outcomes_and_reports_duplicate_ids(tmp_path):
    journal=tmp_path/'backend/cache/trade_journal.jsonl'
    journal.parent.mkdir(parents=True)
    records=[{'trade_id':'same','pnl':1,'session_id':'fixture'},
             {'trade_id':'same','pnl':-1,'session_id':'fixture'},
             {'trade_id':'unknown','session_id':'fixture'}]
    payload=''.join(json.dumps(r)+'\n' for r in records).encode()
    journal.write_bytes(payload)
    session=tmp_path/'logs/paper_trading/session_fixture'
    session.mkdir(parents=True)
    (session/'signals.jsonl').write_text('{"result":"filtered","reason_type":"no_data"}\n')
    (session/'config.json').write_text(json.dumps({'sniper_mode':'stealth','api_key':'synthetic-secret'}))
    report=inspect_history(tmp_path,telemetry_runs=0)
    assert report['journal']['outcomes']=={'reported_positive':1,'reported_negative':1,'unknown':1}
    assert report['journal']['duplicate_trade_ids']=={'same':2}
    assert report['journal']['evidence_key_presence']['frozen_prices']==0
    assert 'synthetic-secret' not in json.dumps(report)
    assert journal.read_bytes()==payload

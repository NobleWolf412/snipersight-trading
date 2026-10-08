"""Persistence checks must follow producers, not historical samples or test SQL."""
import json
import pytest
from pathlib import Path
from backend.diagnostics.storage_contracts import sqlite_tables,writer_contract,capture_storage


def test_nested_sql_constraints_do_not_hide_following_columns():
    source='''db.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY CHECK(id>0), amount DECIMAL(20,8) NOT NULL, label TEXT DEFAULT 'a,b)', UNIQUE(id,label))")'''
    tables,issues=sqlite_tables(source)
    assert not issues and tables[0]['columns']==['amount','id','label']
    assert tables[0]['column_contracts'][1]['type']=='DECIMAL(20,8)'
    assert tables[0]['column_contracts'][1]['not_null']


def test_dynamic_and_multi_statement_ddl_are_visible():
    source='''db.execute(f"CREATE TABLE {name} (id INTEGER)")\ndb.executescript("CREATE TABLE a (id INTEGER); CREATE TABLE b (id INTEGER)")'''
    tables,issues=sqlite_tables(source)
    assert not tables and len(issues)==2


def test_ddl_in_comments_and_documentation_is_not_runtime_storage():
    source='''"""CREATE TABLE docs (fiction TEXT)"""\n# CREATE TABLE comment (fiction TEXT)\ndb.execute("CREATE TABLE real (id INTEGER)")'''
    tables,issues=sqlite_tables(source)
    assert not issues and [t['table'] for t in tables]==['real']


def test_writer_changes_are_detected_but_python_layout_is_not():
    old='def serialize(self):\n    return {"quantity": self.quantity}\n'
    changed=old.replace('"quantity"','"size"')
    assert writer_contract(old,'serialize')!=writer_contract(changed,'serialize')
    assert writer_contract(old,'serialize')==writer_contract(old.replace('    ','  '),'serialize')


def test_inventory_excludes_test_sql_and_never_reads_history(tmp_path,monkeypatch):
    root=tmp_path;backend=root/'backend';backend.mkdir()
    (backend/'store.py').write_text('db.execute("CREATE TABLE real (id INTEGER)")')
    (backend/'tests').mkdir();(backend/'tests'/'fake.py').write_text('db.execute("CREATE TABLE fake (id INTEGER)")')
    (backend/'diagnostics').mkdir();(backend/'diagnostics'/'fake.py').write_text('db.execute("CREATE TABLE probe (id INTEGER)")')
    history=backend/'trade_journal.jsonl';history.write_text('{"old":true}\n')
    original=Path.open
    def guarded(path,*args,**kwargs):
        assert path.suffix!='.jsonl','Historical data must not define current contracts'
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    first=capture_storage(root,writers=())
    assert first['table_count']==1 and not first['unresolved']
    assert first['sqlite_tables'][0]['table']=='real'
    assert json.loads(json.dumps(first))==first


def test_missing_writer_fails_visibly(tmp_path):
    result=capture_storage(tmp_path,writers=(('backend/missing.py','serialize'),))
    assert result['unresolved'] and result['writer_count']==0


def test_existing_checker_uses_sqlite_to_preserve_all_columns():
    from backend.diagnostics.capture_contracts import _parse_create_tables
    source='''db.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY CHECK(id>0), amount DECIMAL(20,8) NOT NULL, label TEXT DEFAULT 'a,b)')")'''
    assert _parse_create_tables(source)[0]['columns']==['amount','id','label']


def test_repository_capture_does_not_open_historical_jsonl(monkeypatch):
    from backend.diagnostics.capture_contracts import capture_db_contracts
    attempts=[];original=Path.open
    def guarded(path,*args,**kwargs):
        if path.suffix=='.jsonl':
            attempts.append(str(path));raise AssertionError('History access')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    result=capture_db_contracts()
    assert not attempts
    assert result['table_count']==6 and not result['unresolved']
    assert result['writer_count']>=9


def test_indirect_ddl_is_unresolved_instead_of_silently_missing():
    source='sql="CREATE TABLE ledger (id INTEGER)"\ndb.execute(sql)'
    tables,issues=sqlite_tables(source)
    assert not tables and issues


@pytest.mark.parametrize('invalid', [{'error':'offline import failed'}, {'error':''}, {'unresolved':['dynamic DDL']}, []])
def test_incomplete_capture_preserves_every_baseline(tmp_path,monkeypatch,invalid):
    from backend.diagnostics import capture_contracts as checker
    good=tmp_path/'good.json';bad=tmp_path/'bad.json'
    good.write_text('{"old":1}');bad.write_text('{"old":2}')
    monkeypatch.setattr(checker,'CONTRACTS_DIR',tmp_path)
    monkeypatch.setattr(checker,'REPO_ROOT',tmp_path)
    monkeypatch.setattr(checker,'CAPTURES', [('good.json','good',lambda:{'new':1}),('bad.json','bad',lambda:invalid)])
    assert checker.cmd_capture()!=0
    assert good.read_text()=='{"old":1}' and bad.read_text()=='{"old":2}'


@pytest.mark.parametrize('invalid', [{'error':'offline import failed'}, {'error':''}, {'unresolved':['dynamic DDL']}, []])
def test_matching_invalid_baseline_cannot_pass_diff(tmp_path,monkeypatch,invalid):
    from backend.diagnostics import capture_contracts as checker
    (tmp_path/'bad.json').write_text(json.dumps(invalid))
    monkeypatch.setattr(checker,'CONTRACTS_DIR',tmp_path)
    monkeypatch.setattr(checker,'REPO_ROOT',tmp_path)
    monkeypatch.setattr(checker,'CAPTURES', [('bad.json','bad',lambda:invalid)])
    assert checker.cmd_diff()!=0


@pytest.mark.parametrize('baseline,current', [
    ([{'table':'events','source':'a.py','columns':['x']},{'table':'events','source':'b.py','columns':['y']}],
     [{'table':'events','source':'a.py','columns':['changed']},{'table':'events','source':'b.py','columns':['y']}]),
    ([{'path':'/api/items','methods':['GET'],'response_model':'Old'},{'path':'/api/items','methods':['POST'],'response_model':'Same'}],
     [{'path':'/api/items','methods':['GET'],'response_model':'New'},{'path':'/api/items','methods':['POST'],'response_model':'Same'}]),
    ([{'name':'same','value':1},{'name':'same','value':2}], [{'name':'same','value':9},{'name':'same','value':2}]),
])
def test_duplicate_names_cannot_hide_contract_drift(baseline,current):
    from backend.diagnostics.capture_contracts import _diff_dicts
    assert _diff_dicts('inventory',baseline,current)


def test_generated_sqlite_columns_remain_in_inventory():
    tables,issues=sqlite_tables('db.execute("CREATE TABLE t (x INTEGER, y INTEGER GENERATED ALWAYS AS (x+1) STORED)")')
    assert not issues and tables[0]['columns']==['x','y']


def test_valid_capture_and_diff_still_succeed(tmp_path,monkeypatch):
    from backend.diagnostics import capture_contracts as checker
    monkeypatch.setattr(checker,'CONTRACTS_DIR',tmp_path)
    monkeypatch.setattr(checker,'REPO_ROOT',tmp_path)
    monkeypatch.setattr(checker,'CAPTURES', [('good.json','good',lambda:{'rows':[{'name':'a','value':1}]})])
    assert checker.cmd_capture()==0 and checker.cmd_diff()==0
    (tmp_path/'good.json').write_text('invalid-json')
    assert checker.cmd_diff()!=0


def test_capture_exception_preserves_baseline(tmp_path,monkeypatch):
    from backend.diagnostics import capture_contracts as checker
    target=tmp_path/'failure.json';target.write_text('{"old":true}')
    def fail():
        raise RuntimeError('deliberate capture failure')
    monkeypatch.setattr(checker,'CONTRACTS_DIR',tmp_path)
    monkeypatch.setattr(checker,'REPO_ROOT',tmp_path)
    monkeypatch.setattr(checker,'CAPTURES', [('failure.json','failure',fail)])
    assert checker.cmd_capture()!=0 and checker.cmd_diff()!=0
    assert target.read_text()=='{"old":true}'

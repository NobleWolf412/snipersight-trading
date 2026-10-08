"""Cumulative partial-exit facts must not be mistaken for completed trade results."""
from dataclasses import replace
from decimal import Decimal as D
import pytest
from backend.bot.executor.execution_outcomes import calculate_progress, calculate_outcome
from backend.tests.unit.test_execution_outcomes import state


@pytest.mark.parametrize('side,exit_cost',[('BUY','420'),('SELL','380')])
@pytest.mark.parametrize('terminal',[True,False])
def test_partial_progress_preserves_actual_cost_and_does_not_require_fees(side,exit_cost,terminal):
    entry=state('entry',side,'10','1000',None)
    child=state('exit','SELL' if side=='BUY' else 'BUY','4',exit_cost,None)
    child=replace(child,status='FILLED' if terminal else 'OPEN',requested_quantity=D(5))
    progress=calculate_progress(entry,(child,))
    assert progress.ready and progress.remaining_quantity==6 and progress.realized_gross==20
    assert not calculate_outcome(entry,(child,)).complete
    assert progress.exits[0].terminal==terminal


@pytest.mark.parametrize('side',["BUY","SELL"])
def test_multiple_partial_exits_are_cumulative_and_full_close_has_no_rounding_residue(side):
    entry=state('entry',side,'3','1000',None)
    other='SELL' if side=='BUY' else 'BUY'
    a=state('a',other,'1','350',None)
    b=state('b',other,'2','700',None)
    first=calculate_progress(entry,(a,))
    final=calculate_progress(entry,(a,b))
    assert first.remaining_quantity==2
    assert final.remaining_quantity==0 and final.realized_gross==(50 if side=='BUY' else -50)
    assert calculate_progress(entry,(a,b))==final


@pytest.mark.parametrize('change,reason',[
    ({'cost':None,'cost_quantity':D(0)},'EXECUTION_COST_UNAVAILABLE'),
    ({'filled_quantity':D(11),'cost_quantity':D(11)},'EXIT_QUANTITY_EXCEEDS_ENTRY'),
    ({'reasons':('VERIFIED_COST_CONFLICT',)},'VERIFIED_COST_CONFLICT'),
])
def test_ambiguous_partial_progress_cannot_authorize_management(change,reason):
    entry=state('entry','BUY','10','1000')
    child=replace(state('exit','SELL','4','420'),**change)
    result=calculate_progress(entry,(child,))
    assert not result.ready and result.realized_gross is None and reason in result.reasons


def test_entry_remainder_must_be_terminal_before_managed_progress():
    entry=replace(state('entry','BUY','10','1000'),status='OPEN')
    result=calculate_progress(entry,(state('exit','SELL','4','420'),))
    assert not result.ready and 'ENTRY_REMAINDER_UNRESOLVED' in result.reasons


@pytest.mark.parametrize('side',['BUY','SELL'])
def test_manager_applies_native_cumulative_slices_once_and_releases_target(side):
    from backend.tests.unit.test_exit_receipts import position
    from backend.bot.executor.position_manager import PositionManager
    from backend.shared.models.planner import Target
    level=105 if side=='BUY' else 95
    pos=position('LONG' if side=='BUY' else 'SHORT',[Target(level=level,percentage=40,rationale='TP1')])
    pos.native_target_order_id='tp';pos.native_target_level=level;pos.native_target_quantity='4'
    mgr=PositionManager(price_fetcher=lambda _:level);mgr.positions[pos.position_id]=pos
    entry=state('entry',side,'10','1000',None)
    tp=replace(state('tp','SELL' if side=='BUY' else 'BUY','1',str(level),None),status='OPEN',requested_quantity=D(4))
    first=calculate_progress(entry,(tp,))
    mgr.reconcile_execution_progress(pos.position_id,first,level)
    mgr.reconcile_execution_progress(pos.position_id,first,level)
    assert pos.remaining_quantity==9 and pos.realized_pnl==5 and pos.targets[0].percentage==30
    assert pos.native_target_order_id=='tp' and not pos.targets_hit
    tp=state('tp',tp.side,'4',str(level*4),None)
    final=calculate_progress(entry,(tp,))
    mgr.reconcile_execution_progress(pos.position_id,final,level)
    mgr.reconcile_execution_progress(pos.position_id,final,level)
    assert pos.remaining_quantity==6 and pos.realized_pnl==20
    assert not pos.native_target_order_id and not pos.targets and len(pos.targets_hit)==1
    assert pos.targets_hit[0].percentage==40


@pytest.mark.parametrize('side',['BUY','SELL'])
def test_cancelled_native_remainder_leaves_only_unfilled_target_quantity(side):
    from backend.tests.unit.test_exit_receipts import position
    from backend.bot.executor.position_manager import PositionManager
    from backend.shared.models.planner import Target
    level=105 if side=='BUY' else 95
    pos=position('LONG' if side=='BUY' else 'SHORT',[Target(level=level,percentage=40,rationale='TP1')])
    pos.native_target_order_id='tp';pos.native_target_level=level;pos.native_target_quantity='4'
    mgr=PositionManager(price_fetcher=lambda _:level);mgr.positions[pos.position_id]=pos
    entry=state('entry',side,'10','1000',None)
    tp=replace(state('tp','SELL' if side=='BUY' else 'BUY','1',str(level),None),status='CANCELLED',requested_quantity=D(4))
    mgr.reconcile_execution_progress(pos.position_id,calculate_progress(entry,(tp,)),level)
    assert pos.remaining_quantity==9 and pos.realized_pnl==5 and pos.targets[0].percentage==30
    assert not pos.native_target_order_id

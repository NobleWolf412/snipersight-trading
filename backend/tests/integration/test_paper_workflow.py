"""Offline integration at the accepted TradePlan boundary; no scanner/ML claims.

Real service, executor, manager, checkpoint and journal. Only quotes, optional
entry observations and the unused model-store boundary are fixtures. No startup,
credentials, exchange transport or persistent application stores are used.
"""
import asyncio
import json
import sys
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock

import pytest

from backend.bot import paper_trading_service as module
from backend.bot.paper_trading_service import PaperBotStatus, PaperTradingConfig, PaperTradingService
from backend.bot.executor.paper_executor import PaperExecutor, OrderStatus, OrderType
from backend.bot.executor.position_manager import PositionManager, PositionStatus
from backend.bot.trade_journal import TradeJournalService
from backend.shared.models.planner import EntryZone, StopLoss, Target, TradePlan
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.defaults import ScanConfig


@pytest.fixture(params=['LONG', 'SHORT'])
def workflow(request, tmp_path, monkeypatch):
    svc = PaperTradingService()
    svc.config = PaperTradingConfig(initial_balance=1000., risk_per_trade=1., leverage=10)
    svc.session_id = 'offline-paper-workflow'
    svc.executor = PaperExecutor(1000., enable_partial_fills=False)
    svc._session_log_dir = tmp_path
    svc._price_cache = {'BTC/USDT': 100., 'ETH/USDT': 100.}
    svc._fetch_price = AsyncMock(side_effect=lambda symbol: svc._price_cache[symbol])
    svc._refresh_price_cache = AsyncMock()  # quotes are advanced explicitly
    svc._inject_cvd_snapshot = Mock()  # no observational exchange poll
    svc.position_manager = PositionManager(
        price_fetcher=lambda symbol: svc._price_cache[symbol],
        order_executor=svc._execute_exit_order,
        receipt_execution=True,
    )
    journal = TradeJournalService(tmp_path/'trades.jsonl')
    monkeypatch.setattr(module, 'get_trade_journal', lambda: journal)
    monkeypatch.setitem(sys.modules, 'backend.ml.model_store',
        S(get_model_store=lambda: S(status=lambda: {'trained': False})))
    direction = request.param
    sign = 1 if direction == 'LONG' else -1

    def plan(symbol='BTC/USDT', targets=None):
        return TradePlan(symbol, direction, 'Day Trade',
            EntryZone(100., 100.-.1*sign, 'fixture entry'),
            StopLoss(100.-sign, 1., 'fixture stop'),
            targets or [Target(100.+3*sign, 'fixture target', percentage=100.)],
            3., confidence_score=90., trade_type='intraday', lot_size=.001)

    return S(svc=svc, journal=journal, plan=plan, sign=sign, path=tmp_path)


def enter(w):
    asyncio.run(w.svc._process_signal(w.plan()))
    positions = w.svc.position_manager.get_open_positions()
    assert len(positions) == 1, w.svc.signal_log
    return positions[0]


def tick(w, monkeypatch):
    async def end_iteration(_):
        w.svc._running = False
    with monkeypatch.context() as context:
        context.setattr(module.asyncio, 'sleep', end_iteration)
        w.svc._running = True
        asyncio.run(w.svc._monitor_loop())


def stop_quote(w):
    w.svc._price_cache['BTC/USDT'] = 100.-2*w.sign


def assert_published(w):
    svc = w.svc
    assert svc.executor.get_position('BTC/USDT') == pytest.approx(0.)
    assert not svc.position_manager.get_open_positions()
    asyncio.run(svc._sync_closed_positions())
    rows = w.journal.query()
    assert len(rows) == 1
    assert svc.stats.total_trades == 1
    assert rows[0]['pnl'] == pytest.approx(svc.executor.balance-1000.)
    assert svc.completed_trades[0].pnl == pytest.approx(rows[0]['pnl'])
    return rows[0]


def test_paper_workflow_full_stop_uses_actual_fill(workflow, monkeypatch):
    w = workflow
    enter(w)
    stop_quote(w)
    tick(w, monkeypatch)
    row = assert_published(w)
    assert row['exit_price'] == pytest.approx(w.svc.executor.fills[-1].price)


@pytest.mark.parametrize('mode_name', ['overwatch', 'strike', 'surgical', 'stealth'])
def test_paper_workflow_strategy_provenance_survives_adaptive_wait_and_exit(workflow, monkeypatch, mode_name):
    from copy import deepcopy
    from backend.analysis.mode_recommendation import AdaptiveModeSelector
    from backend.tests.unit.test_mode_regime_policy import snapshot
    w, svc = workflow, workflow.svc
    mode = get_mode(mode_name)
    svc.config.sniper_mode = mode_name
    svc.mode = mode
    plan = w.plan()
    policy = {'version': 'fixed-playbook-v1', 'mode': mode_name, 'strategy_gate': mode.min_confluence_score}
    plan.metadata = {'strategy': deepcopy(policy)}
    asyncio.run(svc._process_signal(plan))
    pos = svc.position_manager.get_open_positions()[0]
    assert svc.signal_log[-1]['strategy'] == policy
    plan.metadata['strategy']['mode'] = 'mutated'
    assert pos.strategy == policy
    # A new playbook cannot reinterpret an existing trade, even with a flip.
    replacement = w.plan()
    replacement.direction = 'SHORT' if pos.direction == 'LONG' else 'LONG'
    replacement.metadata = {'strategy': {**policy, 'mode': 'strike' if mode_name != 'strike' else 'stealth'}}
    orders_before = len(svc.executor.orders)
    asyncio.run(svc._process_signal(replacement))
    assert len(svc.executor.orders) == orders_before and pos.strategy == policy
    assert 'original playbook' in svc.signal_log[-1]['reason']
    # Stand-aside affects new scans only; the real monitor still executes stops.
    svc.config.selection_mode = 'adaptive'
    svc._adaptive_selector = AdaptiveModeSelector()
    svc._regime_reader = S(get_global=AsyncMock(return_value=snapshot(volatility='chaotic')))
    svc.orchestrator = S(apply_mode=Mock(side_effect=AssertionError('must not scan')))
    asyncio.run(svc._run_scan())
    assert svc.current_scan['status'] == 'waiting'
    assert svc._get_active_positions()[0]['strategy'] == policy
    stop_quote(w)
    tick(w, monkeypatch)
    row = assert_published(w)
    assert row['strategy'] == policy


def test_paper_workflow_pending_plan_keeps_original_mode(workflow):
    svc = workflow.svc
    svc.config.execution_mode = 'rest_maker'
    plan = workflow.plan()
    plan.metadata = {'strategy': {'mode': 'strike', 'version': 'fixed-playbook-v1', 'strategy_gate': 65.}}
    asyncio.run(svc._process_signal(plan))
    before = dict(svc._pending_plans)
    assert len(before) == 1
    replacement = workflow.plan()
    replacement.metadata = {'strategy': {'mode': 'surgical', 'version': 'fixed-playbook-v1', 'strategy_gate': 65.}}
    asyncio.run(svc._process_signal(replacement))
    assert svc._pending_plans == before
    assert len(svc.executor.get_open_orders()) == 1
    assert 'original playbook' in svc.signal_log[-1]['reason']


def test_paper_workflow_partial_stop_stays_owned_until_complete(workflow, monkeypatch):
    w = workflow
    pos = enter(w)
    ex = w.svc.executor
    ex.enable_partial_fills = True
    ex.partial_fill_prob = 1.
    ex.min_fill_pct = ex.max_fill_pct = .5
    stop_quote(w)
    tick(w, monkeypatch)
    assert abs(ex.get_position(pos.symbol)) == pytest.approx(pos.quantity/2)
    assert w.svc.position_manager.get_open_positions(), 'partial exit lost its owner'
    assert not w.journal.query(), 'partial exit published a closed trade'
    state = json.loads((w.path/'state.json').read_text())
    assert state['paper_execution']['positions'][pos.symbol] == ex.get_position(pos.symbol)
    assert state['paper_execution']['pending_exits'][0]['filled_quantity'] == pos.quantity/2
    status = w.svc.get_status()
    assert status['balance']['equity'] == pytest.approx(ex.get_equity(w.svc._price_cache))
    assert status['positions'][0]['remaining_quantity'] == pytest.approx(pos.quantity/2)
    assert pos.remaining_quantity == pos.quantity  # status reads cannot consume the logical slice
    w.svc._peak_equity = 1000.
    expected_drawdown = (1000.-ex.get_equity(w.svc._price_cache))/10.
    assert w.svc._get_current_drawdown_pct() == pytest.approx(expected_drawdown)
    w.svc._update_drawdown()
    assert w.svc.stats.max_drawdown == pytest.approx(expected_drawdown)
    # The exit must complete even after the stop quote recrosses.
    w.svc._price_cache[pos.symbol] = 100.
    ex.enable_partial_fills = False
    tick(w, monkeypatch)
    assert_published(w)
    assert len([o for o in ex.orders.values() if o.order_type == OrderType.MARKET]) == 1


def test_paper_workflow_pending_cap_is_checked_before_fill(workflow, monkeypatch):
    w = workflow
    svc = w.svc
    svc.config.execution_mode = 'rest_maker'
    svc.config.max_positions = 1
    for symbol in ['BTC/USDT', 'ETH/USDT']:
        asyncio.run(svc._process_signal(w.plan(symbol)))
    assert len(svc._pending_plans) == 2
    tick(w, monkeypatch)
    managed = svc.position_manager.get_open_positions()
    assert len(managed) == 1
    assert len([qty for qty in svc.executor.positions.values() if qty]) == 1
    assert not svc._pending_plans
    assert not svc.executor.get_open_orders()


def test_paper_workflow_partial_entry_cannot_refill_after_stop(workflow, monkeypatch):
    w = workflow
    ex = w.svc.executor
    ex.enable_partial_fills = True
    ex.partial_fill_prob = 1.
    ex.min_fill_pct = ex.max_fill_pct = .5
    pos = enter(w)
    entry = ex.get_order(pos.entry_order_id)
    assert entry.status == OrderStatus.PARTIALLY_FILLED
    stop_quote(w)
    # Call management before the service's next limit-fill pass.
    ex.enable_partial_fills = False
    asyncio.run(w.svc.position_manager.monitor_all_positions())
    asyncio.run(w.svc._sync_closed_positions())
    tick(w, monkeypatch)
    assert entry.status == OrderStatus.CANCELLED
    assert_published(w)


@pytest.mark.parametrize('after_write', [False, True])
def test_paper_workflow_journal_retry_preserves_cash_pnl(workflow, monkeypatch, after_write):
    w = workflow
    enter(w)
    original = w.journal.upsert
    def fail(record, session):
        if after_write:
            original(record, session)
        raise OSError('fixture publication failure')
    monkeypatch.setattr(w.journal, 'upsert', fail)
    stop_quote(w)
    tick(w, monkeypatch)
    assert not w.svc.completed_trades
    monkeypatch.setattr(w.journal, 'upsert', original)
    asyncio.run(w.svc._sync_closed_positions())
    assert_published(w)


def test_paper_workflow_shutdown_executes_before_publishing(workflow):
    w = workflow
    enter(w)
    w.svc._price_cache['BTC/USDT'] = 100.+.5*w.sign
    asyncio.run(w.svc._close_all_positions('manual_stop'))
    assert_published(w)


def test_paper_workflow_checkpoint_is_forensic_and_journal_survives_restart(workflow, monkeypatch):
    w = workflow
    pos = enter(w)
    w.svc._save_state()
    state = json.loads((w.path/'state.json').read_text())
    assert state['positions'][0]['entry_order_id'] == pos.entry_order_id
    fresh = PaperTradingService()
    assert fresh.executor is None and fresh.position_manager is None  # no auto-resume claim
    stop_quote(w)
    tick(w, monkeypatch)
    row = assert_published(w)
    reopened = TradeJournalService(w.path/'trades.jsonl')
    assert reopened.query()[0]['pnl'] == row['pnl']
    assert not reopened.upsert(row, w.svc.session_id)
    assert len(reopened.query()) == 1


def test_paper_workflow_partial_target_then_stop_conserves_cash(workflow, monkeypatch):
    w = workflow
    targets = [Target(100.+2*w.sign, 'first', percentage=40.),
               Target(100.+4*w.sign, 'runner', percentage=60.)]
    asyncio.run(w.svc._process_signal(w.plan(targets=targets)))
    pos = w.svc.position_manager.get_open_positions()[0]
    ex = w.svc.executor
    ex.enable_partial_fills = True
    ex.partial_fill_prob = 1.
    ex.min_fill_pct = ex.max_fill_pct = .5
    w.svc._price_cache[pos.symbol] = targets[0].level
    tick(w, monkeypatch)
    assert abs(ex.get_position(pos.symbol)) == pytest.approx(pos.quantity*.8)
    assert pos.pending_target is not None and not pos.targets_hit
    ex.enable_partial_fills = False
    w.svc._price_cache[pos.symbol] = 100.+w.sign  # target recrossed
    tick(w, monkeypatch)
    assert len(pos.targets_hit) == 1 and pos.remaining_quantity == pytest.approx(pos.quantity*.6)
    assert pos.pending_target is None
    stop_quote(w)
    tick(w, monkeypatch)
    assert_published(w)


def test_paper_workflow_additional_entry_fills_keep_one_owner(workflow, monkeypatch):
    w = workflow
    ex = w.svc.executor
    ex.enable_partial_fills = True
    ex.partial_fill_prob = 1.
    ex.min_fill_pct = ex.max_fill_pct = .5
    pos = enter(w)
    first_qty = pos.quantity
    ex.enable_partial_fills = False
    tick(w, monkeypatch)
    assert pos.quantity == pytest.approx(first_qty*2)
    assert len(w.svc.position_manager.get_open_positions()) == 1
    assert abs(ex.get_position(pos.symbol)) == pytest.approx(pos.remaining_quantity)
    stop_quote(w)
    tick(w, monkeypatch)
    assert_published(w)


def test_paper_workflow_direction_flip_finishes_pending_exit_without_new_signal(workflow, monkeypatch):
    w = workflow
    pos = enter(w)
    ex = w.svc.executor
    ex.enable_partial_fills = True
    ex.partial_fill_prob = 1.
    ex.min_fill_pct = ex.max_fill_pct = .5
    opposite = w.plan()
    opposite.direction = 'SHORT' if pos.direction == 'LONG' else 'LONG'
    # Exit precedes admission of the replacement plan; no replacement is emitted.
    asyncio.run(w.svc._process_signal(opposite))
    assert pos.pending_exit_reason == 'DIRECTION_FLIP'
    assert not w.svc.completed_trades
    ex.enable_partial_fills = False
    tick(w, monkeypatch)
    assert_published(w)


@pytest.mark.parametrize('partial', [False, True])
@pytest.mark.parametrize('immediate', [False, True])
@pytest.mark.parametrize('recovery', ['monitor', 'stop'])
def test_paper_workflow_failed_adoption_is_retried_from_cumulative_fill(workflow, monkeypatch, partial, immediate, recovery):
    w = workflow
    svc = w.svc
    svc.config.execution_mode = 'snap_taker' if immediate else 'rest_maker'
    ex = svc.executor
    ex.enable_partial_fills = partial
    ex.partial_fill_prob = 1.
    ex.min_fill_pct = ex.max_fill_pct = .5
    original = svc.position_manager.open_position
    monkeypatch.setattr(svc.position_manager, 'open_position', Mock(side_effect=RuntimeError('fixture adoption failure')))
    asyncio.run(svc._process_signal(w.plan()))
    if not immediate:
        tick(w, monkeypatch)
    filled = abs(ex.get_position('BTC/USDT'))
    assert filled > 0 and svc._pending_plans
    assert not svc.position_manager.get_open_positions()
    monkeypatch.setattr(svc.position_manager, 'open_position', original)
    if recovery == 'monitor':
        tick(w, monkeypatch)
        pos = svc.position_manager.get_open_positions()[0]
        assert pos.quantity == pytest.approx(filled)
        assert not svc._pending_plans
    ex.enable_partial_fills = False
    asyncio.run(svc._close_all_positions('manual_stop'))
    assert_published(w)


def test_paper_workflow_stop_retries_partial_exit_and_retains_failures(workflow, monkeypatch):
    w = workflow
    pos = enter(w)
    ex = w.svc.executor
    w.svc.status = PaperBotStatus.RUNNING
    ex.enable_partial_fills = True
    ex.partial_fill_prob = 1.
    ex.min_fill_pct = ex.max_fill_pct = .5
    original = ex.execute_market_order
    monkeypatch.setattr(ex, 'execute_market_order', Mock(return_value=None))
    status = asyncio.run(w.svc.stop())
    assert status['status'] == 'error'
    assert status['recovery_required']
    assert not w.svc.get_status()['reset_allowed']
    assert pos.remaining_quantity > 0 and not w.journal.query()
    with pytest.raises(ValueError, match='PAPER_RECOVERY_REQUIRED'):
        w.svc.reset()
    with pytest.raises(ValueError, match='PAPER_RECOVERY_REQUIRED'):
        asyncio.run(w.svc.start(w.svc.config))
    monkeypatch.setattr(ex, 'execute_market_order', original)
    status = asyncio.run(w.svc.stop())
    assert status['status'] == 'stopped'
    assert not w.svc.get_status()['recovery_required']
    assert w.svc.get_status()['reset_allowed']
    assert_published(w)
    assert len([o for o in ex.orders.values() if o.order_type == OrderType.MARKET]) == 1


@pytest.mark.parametrize('kind', ['LIMIT', 'MARKET'])
def test_paper_workflow_cancelled_orders_cannot_fill_again(workflow, kind):
    ex = workflow.svc.executor
    order = ex.place_order('BTC/USDT', 'BUY', kind, 1., price=100.)
    assert ex.cancel_order(order.order_id)
    fill = ex.execute_limit_order(order.order_id, 100.) if kind == 'LIMIT' else ex.execute_market_order(order.order_id, 100.)
    assert fill is None and not ex.fills and ex.balance == 1000.


@pytest.mark.parametrize('accepted', [True, False])
def test_paper_workflow_scanner_result_handoff(workflow, monkeypatch, accepted):
    # Exercise the real bot scan wrapper and everything downstream. The scanner
    # result is explicit fixture input: this does not validate SMC/scoring itself.
    w = workflow
    svc = w.svc
    svc.config.symbols = ['BTC/USDT']
    svc.mode = get_mode('stealth')
    scan = Mock(return_value=([w.plan()] if accepted else [], {
        'regime': {'composite': 'sideways_normal', 'trend': 'sideways',
                   'volatility': 'normal', 'score': 70},
        'details': {}, 'by_reason': {},
    }))
    svc.orchestrator = S(
        config=ScanConfig(), apply_mode=Mock(), scan_with_heartbeat=scan,
        regime_detector=S(get_confirmed_regime=lambda: None),
        exchange_adapter=S(get_symbol_volumes=lambda symbols: {s: 100_000_000. for s in symbols}),
        register_stop_out=Mock(),
    )
    asyncio.run(svc._run_scan())
    scan.assert_called_once()
    assert svc.stats.signals_generated == int(accepted)
    assert len(svc.position_manager.get_open_positions()) == int(accepted), svc.activity_log
    if accepted:
        stop_quote(w)
        tick(w, monkeypatch)
        assert_published(w)
        svc.orchestrator.register_stop_out.assert_called_once()
    else:
        assert not svc.executor.orders and not w.journal.query()


def test_paper_workflow_journal_cash_is_separated_across_immediate_direction_flip(workflow, monkeypatch):
    w = workflow
    first = enter(w)
    before = w.svc.executor.balance
    opposite = TradePlan('BTC/USDT', 'SHORT' if w.sign == 1 else 'LONG', 'Day Trade',
        EntryZone(100., 100.+.1*w.sign, 'replacement entry'),
        StopLoss(100.+w.sign, 1., 'replacement stop'),
        [Target(100.-3*w.sign, 'replacement target', percentage=100.)],
        3., confidence_score=90., trade_type='intraday', lot_size=.001)
    asyncio.run(w.svc._process_signal(opposite))
    assert len(w.svc.position_manager.positions) == 2
    asyncio.run(w.svc._sync_closed_positions())
    assert len(w.journal.query()) == 1
    entry_fee = w.svc.executor.fills[0].fee
    exit_fill = w.svc.executor.fills[1]
    first_net = (exit_fill.price-first.entry_price)*w.sign*first.quantity-entry_fee-exit_fill.fee
    assert w.journal.query()[0]['pnl'] == pytest.approx(first_net)
    assert w.svc.executor.balance < before  # two sets of fees/slippage are real
    w.svc._price_cache['BTC/USDT'] = 100.+2*w.sign
    tick(w, monkeypatch)
    assert len(w.journal.query()) == 2
    assert sum(row['pnl'] for row in w.journal.query()) == pytest.approx(w.svc.executor.balance-1000.)
    assert w.svc.executor.get_position('BTC/USDT') == pytest.approx(0.)

"""Offline evidence probes for decision-input defects; never fetches market data.

Controlled fixtures exercise production functions. Results describe these fixtures,
not live market conditions or strategy performance. Run under the audit's isolated
verification harness when importing the full backend in an existing installation.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd


def inspect_inputs() -> dict:
    from backend.analysis import dominance_service as dominance
    from backend.analysis import regime_detector as regime_module
    from backend.engine import orchestrator as module
    from backend.engine.orchestrator import Orchestrator
    from backend.engine.replay_engine import ReplayEngine
    from backend.services.smc_service import SMCDetectionService
    from backend.shared.config.defaults import ScanConfig
    from backend.shared.config.scanner_modes import get_mode
    from backend.shared.models.data import MultiTimeframeData
    from backend.shared.models.smc import OrderBlock

    report = {'scope': 'controlled offline fixtures; no performance inference', 'observations': {}}
    seen = report['observations']
    now = datetime(2001, 2, 5, 8, tzinfo=timezone.utc)
    with ExitStack() as stack:
        stack.enter_context(patch.object(module, 'get_telemetry_logger', return_value=SimpleNamespace(log_event=lambda *a, **k: None)))
        stack.enter_context(patch.object(module, 'CooldownManager', return_value=object()))
        stack.enter_context(patch.object(regime_module, '_regime_detector', None))
        for package, variable in [('indicator_service', '_indicator_service'), ('smc_service', '_smc_service'), ('confluence_service', '_confluence_service')]:
            package_module = __import__('backend.services.' + package, fromlist=[variable])
            stack.enter_context(patch.object(package_module, variable, None))

        # The complete selected-mode transition uses actual service implementations.
        orch = Orchestrator(ScanConfig(profile='stealth_balanced'), exchange_adapter=object())
        transitions = []
        for name in ('stealth', 'strike', 'overwatch', 'surgical'):
            orch.apply_mode(get_mode(name))
            transitions.append(dict(requested=name, config_profile=orch.config.profile,
                                    smc_mode=orch.smc_service._mode,
                                    smc_profile=orch.smc_service._mode_profile,
                                    detector_profile=orch.regime_detector.mode_profile))
        seen['mode_propagation'] = transitions

        # Missing dominance currently crosses two production functions.
        with patch.object(dominance, 'get_current_dominance', return_value=None):
            try:
                values = dominance.get_dominance_for_macro()
                value_error = None
            except ValueError as error:
                values, value_error = None, str(error)
            try:
                label, score = regime_module.RegimeDetector()._detect_risk_appetite()
                classification_error = None
            except ValueError as error:
                label, score, classification_error = None, None, str(error)
        seen['missing_dominance'] = dict(values=values, label=label, score=score,
                                         value_error=value_error, classification_error=classification_error)

        # The read API returns arbitrarily stale cached evidence after fetch failure.
        service = object.__new__(dominance.DominanceService)
        service._load_cache = lambda: dict(timestamp=1., btc_dom=54., alt_dom=42., stable_dom=4.)
        service._fetch_market_caps = lambda **kwargs: None
        stale = service.get_dominance()
        seen['dominance_stale_fallback'] = dict(timestamp=stale.timestamp, btc_dom=stale.btc_dom)

        # A replay step changes solely because the present-day dominance fixture changes.
        replay = ReplayEngine(object())._build_orchestrator(get_mode('stealth'))
        detector = replay.regime_detector
        detector._detect_trend = lambda data: ('up', 70.)
        detector._detect_volatility = lambda indicators: ('normal', 75.)
        detector._detect_liquidity = lambda data: ('healthy', 70.)
        detector._apply_hysteresis = lambda regime: regime
        replay.indicator_service = SimpleNamespace(compute=lambda data: SimpleNamespace(by_timeframe={'1h': object()}))
        replay._process_symbol = lambda **kwargs: (None, None)
        replay_observations = []
        for btc_dom, stable_dom in ((51., 3.), (60., 7.)):
            snapshot = SimpleNamespace(btc_dom=btc_dom, alt_dom=100.-btc_dom-stable_dom, stable_dom=stable_dom)
            with patch.object(dominance, 'get_current_dominance', return_value=snapshot):
                replay.process_symbol_for_replay('BTC/USDT', None, now, 'probe', 0, 'fixture',
                                                 prefetched_btc_data=SimpleNamespace(timeframes={'1h': object()}))
            current = replay.current_regime
            replay_observations.append(dict(as_of=now.isoformat(),
                                            risk=current.dimensions.risk_appetite if current else None,
                                            risk_score=current.risk_score if current else None,
                                            current_classifier_used=current is not None))
        seen['replay_current_dominance'] = replay_observations

        frame = pd.DataFrame(dict(open=100., high=110., low=90., close=100., volume=10.),
                             index=pd.date_range('2001-02-03', periods=30, freq='h'))
        frame['timestamp'] = frame.index
        mitigation = []
        for direction in ('bullish', 'bearish'):
            for timeframe in ('15m', '1h'):
                data = MultiTimeframeData('BTC/USDT', {timeframe: frame})
                block = OrderBlock(timeframe='1h', direction=direction, high=101., low=99.,
                                   timestamp=datetime(2001, 2, 2), displacement_strength=80.,
                                   mitigation_level=0., freshness_score=100.)
                remaining = SMCDetectionService()._update_mitigation(data, [block], as_of=now)
                mitigation.append(dict(direction=direction, available=timeframe, surviving=len(remaining)))
        seen['mitigation_dataframe_selection'] = mitigation

        # Execute the actual cycle try-body to identify the unavailable calculation.
        tree = ast.parse(inspect.getsource(module))
        candidate = next(node for node in ast.walk(tree) if isinstance(node, ast.Try)
                         and node.body and isinstance(node.body[0], ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == 'cycle_tf' for target in node.body[0].targets))
        code = compile(ast.fix_missing_locations(ast.Module(body=candidate.body, type_ignores=[])),
                       'production-cycle-try-body', 'exec')
        cycle = []
        for primary in ('1h', '4h'):
            namespace = dict(module.__dict__, self=SimpleNamespace(config=SimpleNamespace(primary_planning_timeframe=primary)),
                             context=SimpleNamespace(multi_tf_data=SimpleNamespace(timeframes={'1h': frame})),
                             current_price_val=100., symbol='BTC/USDT')
            try:
                exec(code, namespace)
            except Exception as error:
                cycle.append(dict(primary=primary, exception=type(error).__name__, message=str(error)))
        seen['cycle_context_calculation_errors'] = cycle
        seen['remaining_semantics'] = inspect_remaining_semantics()
    return report


def inspect_remaining_semantics() -> dict:
    """Controlled probes of unresolved semantics, without selecting new policies."""
    from backend.services import confluence_service
    from backend.bot.paper_trading_service import PaperTradingService
    from backend.analysis.regime_policies import get_regime_policy
    from backend.shared.models.regime import MarketRegime, RegimeDimensions, SymbolRegime
    from backend.analysis.regime_detector import RegimeDetector
    from backend.engine import decision

    tree = ast.parse(inspect.getsource(confluence_service))
    bonus = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == 'global_regime and symbol_regime')
    compiled = compile(ast.fix_missing_locations(ast.Module(body=[bonus], type_ignores=[])),
                       'production-htf-bonus', 'exec')
    aligned = []
    sizes = []
    for direction, trend in (('LONG', 'up'), ('SHORT', 'down')):
        global_regime = MarketRegime(
            RegimeDimensions(trend, 'normal', 'healthy', 'risk_on', 'balanced'),
            f'strong_{trend}_normal', 75., datetime(2001, 1, 1), 75., 75., 75., 75., 50.)
        local = SymbolRegime('BTC/USDT', trend, 'normal', 75.)
        context = SimpleNamespace(symbol='BTC/USDT', metadata={})
        chosen = SimpleNamespace(total_score=70.)
        exec(compiled, dict(confluence_service.__dict__, global_regime=global_regime,
                            symbol_regime=local, context=context, chosen=chosen,
                            chosen_direction=direction))
        aligned.append(dict(direction=direction, actual_global_trend=trend,
                            evaluated_bonus=context.metadata.get('htf_alignment_bonus'),
                            resulting_score=chosen.total_score))
        service = object.__new__(PaperTradingService)
        service._current_regime_policy = get_regime_policy('stealth')
        service._current_regime_composite = f'strong_{trend}_normal'
        service._current_regime_score = 75.
        sizes.append(dict(composite=service._current_regime_composite,
                          multiplier=service._get_regime_size_multiplier()))
    volatility = []
    for name, atr, price in [('valid', 3., 100.), ('no_price', 3., None), ('nonfinite', float('nan'), 100.)]:
        snap = SimpleNamespace(atr=atr, bb_middle=None, dataframe=None if price is None else pd.DataFrame({'close':[price]}))
        try:
            label, score = RegimeDetector()._detect_volatility(SimpleNamespace(by_timeframe={'1d':snap}))
            volatility.append(dict(case=name, label=label, score=score))
        except ValueError as error:
            volatility.append(dict(case=name, error=str(error)))
    with patch.dict('os.environ', {'SS_DECISION_POLICY':'legacy'}):
        policy = decision.active_decision_policy()
        cached = decision.is_thesis_mode()
        with patch.dict('os.environ', {'SS_DECISION_POLICY':'thesis'}):
            flag = dict(policy_at_construction=policy.name, cached_gate=cached,
                        later_dynamic_gate=decision.is_thesis_mode())
    # Selection intentionally has backfill in older tests, but its exclusion
    # report claims a contradictory result. Preserve behavior and expose both.
    from backend.analysis import pair_selection as pairs
    fixture_symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'ADA/USDT']
    adapter = SimpleNamespace(get_top_symbols=lambda **kwargs: fixture_symbols)
    with patch.object(pairs, '_is_meme_symbol', side_effect=lambda s: s == 'DOGE/USDT'), \
         patch.object(pairs, 'is_symbol_stale', return_value=False), \
         patch.object(pairs, '_write_snapshot'):
        selected, dropped = pairs.select_symbols_with_drops(
            adapter, limit=10, majors=True, altcoins=False, meme_mode=False,
        )
    universe = dict(selected=selected, dropped=dropped,
                    selected_and_excluded=sorted(set(selected) & {d['symbol'] for d in dropped}))

    # Match the journal query's descending order with synthetic dated records.
    # No saved model, actual journal or training process is opened.
    from backend.ml.feature_extractor import build_dataset
    from backend.ml.edge_model import PurgedWalkForwardCV
    records = [dict(trade_id=str(i), entry_time=f'2001-02-{i:02d}T00:00:00+00:00',
                    confidence_score=75., pnl=1., exit_reason='target')
               for i in range(28, 0, -1)]
    features, labels, weights, ids = build_dataset(records)
    train, test = next(PurgedWalkForwardCV(n_splits=2).split(features))
    chronology = dict(input_order='journal-style newest first',
                      first_training_id=ids[train[0]], first_test_id=ids[test[0]],
                      training_contains_later_events=int(ids[train[0]]) > int(ids[test[0]]),
                      timestamp_sort_applied=ids != [r['trade_id'] for r in records])
    return dict(global_dimension_bonus=aligned, size_substring_precedence=sizes,
                volatility_validity=volatility, mutable_flag_consistency=flag,
                universe_backfill_reporting=universe, ml_fold_chronology=chronology)


def main():
    print(json.dumps(inspect_inputs(), indent=2))


if __name__ == '__main__':
    main()

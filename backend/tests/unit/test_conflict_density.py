"""Conflict counts describe current mode-scoped evidence, not event history."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as S

import pytest

from backend.shared.config.scanner_modes import get_mode
from backend.shared.models.smc import FVG, OrderBlock, SMCSnapshot, StructuralBreak
from backend.strategy.confluence.scorer import run_pre_scoring_gates


NOW = datetime(2026, 10, 10, 15, tzinfo=timezone.utc)


def brk(tf='4h', direction='bearish', hour=0, kind='BOS', level=100.):
    return StructuralBreak(tf, kind, level, NOW + timedelta(hours=hour), False,
                           direction=direction)


def zone(low=100., high=110., tf='4h', direction='bearish', **kw):
    return OrderBlock(tf, direction, high, low, NOW, 80., 0., 80., grade='A', **kw)


def gate(breaks=(), zones=(), direction='LONG', mode='stealth', config=None, **kw):
    aligned = 'bullish' if direction == 'LONG' else 'bearish'
    anchor = FVG('1h', aligned, 102., 100., NOW, 2., 0., grade='A', size_atr=2.)
    return run_pre_scoring_gates(SMCSnapshot(list(zones), [anchor], list(breaks), []),
                                config or get_mode(mode), direction, **kw)


@pytest.mark.parametrize('direction,opposed', [('LONG', 'bearish'), ('SHORT', 'bullish')])
def test_conflict_density_ondo_history_is_two_states_not_four_conditions(direction, opposed):
    # Recorded ONDO scan400 levels; times here deliberately synthetic because
    # the rejection log did not retain full detector timestamps.
    events = [brk('1H', opposed, level=.4551), brk('4H', opposed, -3, level=.3643),
              brk('4H', opposed, -2, level=.3385), brk('4H', opposed, -1, level=.4551)]
    result = gate(events, direction=direction)
    assert result.passed
    assert result.metadata['conflict_count'] == 2
    assert result.metadata['conflict_threshold'] == 3


@pytest.mark.parametrize('kind', ['BOS', 'CHoCH'])
@pytest.mark.parametrize('direction,opposed,aligned', [('LONG', 'bearish', 'bullish'), ('SHORT', 'bullish', 'bearish')])
def test_conflict_density_later_structure_replaces_old_opposition(kind, direction, opposed, aligned):
    events = [brk('4h', opposed, -5), brk('4h', opposed, -4), brk('4h', opposed, -3),
              brk('4h', aligned, -1, kind)]
    assert gate(events, direction=direction).metadata['conflict_count'] == 0
    assert gate(list(reversed(events)), direction=direction).metadata['conflict_count'] == 0


def test_conflict_density_latest_choch_is_not_an_extra_bos_conflict():
    assert gate([brk(hour=-1), brk(kind='CHoCH')]).metadata['conflict_count'] == 0


@pytest.mark.parametrize('mode', ['overwatch', 'stealth', 'strike', 'surgical'])
def test_conflict_density_uses_effective_mode_structure_scope(mode):
    mode_cfg = get_mode(mode)
    allowed = mode_cfg.structure_timeframes
    events = [brk(tf) for tf in ['1w', '1d', '4h', '1h', '15m', '5m', '1m']]
    result = gate(events, mode=mode)
    assert result.metadata['conflict_count'] == len(allowed)
    assert result.metadata['conflict_timeframes'] == sorted(allowed)
    assert result.metadata['conflict_threshold'] == (5 if mode == 'overwatch' else 3)


def test_conflict_density_scope_precedence_and_case_normalization():
    cfg = S(profile='stealth_balanced', structure_timeframes=('1H',))
    events = [brk(tf) for tf in ['1H', '4H', '1D']]
    assert gate(events, config=cfg).metadata['conflict_count'] == 1
    assert gate(events, config=cfg, relevant_timeframes={'4H', '1D'}).metadata['conflict_count'] == 2
    assert gate(events, config=cfg, relevant_timeframes=set()).metadata['conflict_count'] == 0
    assert gate(events, config=S(profile='macro_surveillance')).metadata['conflict_count'] == 2


@pytest.mark.parametrize('direction,opposed', [('LONG', 'bearish'), ('SHORT', 'bullish')])
def test_conflict_density_distinct_timeframes_still_block_at_three(direction, opposed):
    result = gate([brk(tf, opposed) for tf in ['15m', '1h', '4h']], direction=direction)
    assert not result.passed and result.gate_name == 'conflict_density'
    assert result.metadata['conflict_count'] == 3
    assert len(result.metadata['conflict_conditions']) == 3
    assert 'threshold 3' in result.reason


@pytest.mark.parametrize('direction,opposed', [('LONG', 'bearish'), ('SHORT', 'bullish')])
def test_conflict_density_ob_lifecycle(direction, opposed):
    zones = [zone(direction=opposed, breaker=True), zone(direction=opposed, invalidated=True),
             replace(zone(direction=opposed), mitigation_level=1.),
             replace(zone(direction=opposed), grade='C')]
    assert gate(zones=zones, direction=direction).metadata['conflict_count'] == 0


def test_conflict_density_duplicate_nested_zones_across_timeframes_count_once():
    zones = [zone(100., 120., '4h'), zone(105., 110., '1h'), zone(105., 110., '15m')]
    a = gate(zones=zones)
    b = gate(zones=list(reversed(zones)))
    assert a.metadata == b.metadata
    assert a.passed and a.metadata['conflict_count'] == 1
    label = a.metadata['conflict_conditions'][0]
    assert '100' in label and '120' in label
    assert all(tf in label for tf in ['4h', '1h', '15m'])


def test_conflict_density_overlap_bridge_does_not_merge_disjoint_obstacles():
    # A/B and B/C overlap >50%; A/C do not. A bridge cannot collapse all three.
    zones = [zone(100., 110.), zone(104., 114.), zone(108., 118.)]
    assert gate(zones=zones).metadata['conflict_count'] == 2
    assert gate(zones=list(reversed(zones))).metadata['conflict_count'] == 2


def test_conflict_density_half_overlap_and_touching_zones_remain_distinct():
    assert gate(zones=[zone(100., 110.), zone(105., 115.)]).metadata['conflict_count'] == 2
    assert gate(zones=[zone(100., 110.), zone(110., 120.)]).metadata['conflict_count'] == 2


def test_conflict_density_overwatch_limit_remains_reachable_after_dedup():
    events = [brk(tf) for tf in ['4h', '1d', '1w']]
    zones = [zone(100., 110.), zone(120., 130.)]
    assert gate(events, zones[:1], mode='overwatch').passed
    result = gate(events, zones, mode='overwatch')
    assert not result.passed and result.metadata['conflict_count'] == 5


def test_conflict_density_does_not_reassign_upstream_freshness_or_price_policy():
    # Gate consumes the detector's mode-filtered snapshot. No new age/price cutoff.
    zones = [replace(zone(), freshness_score=20., mitigation_level=.3)]
    assert gate(zones=zones).metadata['conflict_count'] == 1


def test_conflict_density_latest_timestamp_ties_are_order_independent():
    events = [brk(direction='bullish'), brk(direction='bearish')]
    for direction in ['LONG', 'SHORT']:
        a = gate(events, direction=direction)
        b = gate(list(reversed(events)), direction=direction)
        assert a.metadata == b.metadata
        assert a.metadata['conflict_count'] == 1


def test_conflict_density_labels_include_event_time_and_real_ob_boundaries():
    result = gate([brk('1h'), brk('4h')], [zone(120., 130.)])
    assert NOW.isoformat() in result.metadata['conflict_conditions'][0]
    assert '120' in result.metadata['conflict_conditions'][-1]
    assert '130' in result.metadata['conflict_conditions'][-1]


def test_conflict_density_captured_feed_reduces_history_to_current_states(capsys):
    """Reuse saved public candles; not the original rejected scan's full inputs."""
    import json
    from pathlib import Path
    import pandas as pd
    from backend.services.smc_service import SMCDetectionService
    from backend.shared.config.smc_config import get_tf_smc_config
    from backend.strategy.smc.bos_choch import detect_structural_breaks

    captures = Path(__file__).resolve().parents[3] / 'docs/audits/structural_gate_2026-10-10'
    events = []
    for tf, duration in [('15m', '15min'), ('1h', '1h'), ('4h', '4h'), ('1d', '1D')]:
        payload = json.loads((captures / f'btc_{tf}.json').read_text())
        df = pd.DataFrame(payload['candles'])
        df.index = pd.to_datetime(df.pop('timestamp'), utc=True)
        df = df[df.index + pd.Timedelta(duration) <= pd.Timestamp(payload['capture']['analysis_cutoff'])]
        config = SMCDetectionService(mode='stealth')._create_tf_smc_config(get_tf_smc_config(tf, 'stealth'))
        events.extend(detect_structural_breaks(df, config, mode_profile='stealth_balanced'))
    assert events
    rows = []
    for direction, opposed in [('LONG', 'bearish'), ('SHORT', 'bullish')]:
        old_count = sum(e.break_type == 'BOS' and e.direction == opposed for e in events)
        result = gate(events, direction=direction)
        new_count = result.metadata['conflict_count']
        assert new_count <= 4 and new_count <= old_count
        rows.append({'direction': direction, 'historical_bos_count': old_count,
                     'current_state_count': new_count, 'conditions': result.metadata['conflict_conditions']})
    assert sum(r['current_state_count'] for r in rows) < sum(r['historical_bos_count'] for r in rows)
    with capsys.disabled():
        print('CONFLICT_CAPTURE ' + json.dumps(rows))

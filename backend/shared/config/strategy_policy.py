"""Fixed playbook identity and bot restrictions shared by scanner and bot paths."""
from copy import deepcopy

from backend.shared.config.scanner_modes import get_mode, get_macd_config, get_volume_profile_config
from backend.shared.config.score_policy import SCORE_MODEL_VERSION, SCORE_POLICY_VERSION
from backend.shared.config.sensitivity import resolve_sensitivity

PLAYBOOK_VERSION = "fixed-playbook-v1"


def validate_strategy_selection(config, *, paper=False):
    mode = get_mode(config.sniper_mode)
    config.sniper_mode = mode.name
    selection = getattr(config, "selection_mode", "fixed")
    if selection not in ("fixed", "adaptive"):
        raise ValueError("Unknown strategy selection setting")
    if selection == "adaptive":
        if not paper or getattr(config, "use_testnet", False):
            raise ValueError("Adaptive selection is supported only in simulated paper trading")
        allowed = getattr(config, "allowed_modes", ())
        if not allowed:
            raise ValueError("Adaptive selection requires at least one allowed mode")
        config.allowed_modes = list(dict.fromkeys(get_mode(name).name for name in allowed))
    resolve_bot_sensitivity(config, mode.min_confluence_score)
    return mode


def resolve_bot_sensitivity(config, strategy_gate):
    """A stricter bot can reduce size, but never waive mode qualification."""
    gate, floor, preset = resolve_sensitivity(config, strategy_gate)
    return max(strategy_gate, gate), max(strategy_gate, floor), preset


def strategy_snapshot(mode, config):
    return {
        "version": PLAYBOOK_VERSION, "mode": mode.name, "profile": mode.profile,
        "score_model": SCORE_MODEL_VERSION, "score_policy": SCORE_POLICY_VERSION,
        "selection_mode": getattr(config, "selection_mode", "fixed"),
        "strategy_gate": mode.min_confluence_score,
        "effective_gate": max(mode.min_confluence_score, config.min_confluence_score),
        "full_size_gate": getattr(config, "bot_full_size_gate", None),
        "timeframes": list(config.timeframes),
        "planning_timeframe": config.primary_planning_timeframe,
        "structure_timeframes": list(config.structure_timeframes),
        "entry_timeframes": list(config.entry_timeframes),
        "zone_timeframes": list(config.zone_timeframes),
        "entry_trigger_timeframes": list(config.entry_trigger_timeframes),
        "overrides": deepcopy(config.overrides),
        "stop_timeframes": list(config.stop_timeframes),
        "target_timeframes": list(config.target_timeframes),
        "macd_settings": list(get_macd_config(mode.profile).macd_settings),
        "volume_profile": list(get_volume_profile_config(mode.name)),
        "recommendation": deepcopy(getattr(config, "mode_recommendation", None)),
    }


def plan_strategy_gate(plan, fallback_mode):
    snapshot = (getattr(plan, "metadata", None) or {}).get("strategy") or {}
    mode = get_mode(snapshot.get("mode") or fallback_mode)
    # Recorded policies cannot weaken the current supported playbook baseline.
    return max(mode.min_confluence_score, float(snapshot.get("strategy_gate", 0.)))

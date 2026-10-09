"""Resolve bot score thresholds identically at startup, scan and entry."""
import math
from backend.shared.config.score_policy import BOT_SCORE_PRESETS as SENSITIVITY_PRESETS


def passes_confluence_gate(score: float, gate: float) -> bool:
    """One-decimal admission comparison shared by scanner, labels and bots.

    The gate is a heuristic score cutoff. Invalid scores cannot pass, even
    when a caller intentionally sets a zero cutoff for diagnostics.
    """
    if isinstance(gate, bool) or not isinstance(gate, (int, float)) or not math.isfinite(gate) or not 0 <= gate <= 100:
        raise ValueError("Confluence gate must be finite and within [0, 100]")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100:
        return False
    return round(score, 1) >= round(gate, 1)


def resolve_sensitivity(config, mode_gate: float) -> tuple[float, float, str]:
    """Explicit values win; otherwise use the preset, then the mode for custom.

    An explicit gate without a floor uses a ten-point band (including gate=0).
    These are heuristic score thresholds, not probabilities of winning.
    """
    preset = (getattr(config, "sensitivity_preset", None) or "balanced").strip().lower()
    if preset not in (*SENSITIVITY_PRESETS, "custom"):
        raise ValueError(f"Unknown sensitivity preset: {preset}")
    explicit_gate = getattr(config, "min_confluence", None)
    gate = explicit_gate if explicit_gate is not None else SENSITIVITY_PRESETS.get(preset, {}).get("gate", mode_gate)
    if isinstance(gate, bool) or not isinstance(gate, (int, float)) or not math.isfinite(gate) or not 0 <= gate <= 100:
        raise ValueError("Confluence gate must be finite and within [0, 100]")
    floor = getattr(config, "confluence_soft_floor", None)
    if floor is None:
        floor = (SENSITIVITY_PRESETS[preset]["floor"]
                 if explicit_gate is None and preset in SENSITIVITY_PRESETS else max(0., gate - 10.))
    if isinstance(floor, bool) or not isinstance(floor, (int, float)) or not math.isfinite(floor) or not 0 <= floor <= gate:
        raise ValueError("Confluence floor must be finite and within [0, gate]")
    return float(gate), float(floor), preset

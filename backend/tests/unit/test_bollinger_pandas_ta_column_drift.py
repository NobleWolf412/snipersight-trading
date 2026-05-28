"""
Regression test for the pandas-ta Bollinger Bands column-naming drift bug
(calibrated 2026-05-27 — operator flagged "pandas-ta Bollinger Bands failed,
falling back to manual implementation" warning spam in production logs).

The pandas-ta library changed its bbands() column naming convention between
versions:
  - older: BBL_20_2.0 / BBM_20_2.0 / BBU_20_2.0
  - newer: BBL_20_2.0_2.0 / BBM_20_2.0_2.0 / BBU_20_2.0_2.0  (std arg duplicated)

The pre-fix code hard-coded the old format, never matched, and silently
fell back to a manual implementation that used pandas' default ddof=1
(sample std) — producing ~2.6% wider bands than pandas-ta at period=20.

The fix at backend/indicators/volatility.py:175-220:
  1. Match columns by PREFIX (BBU_{period}_, BBM_{period}_, BBL_{period}_)
     instead of exact-name lookup — robust across version bumps
  2. Manual fallback now uses ddof=0 (population std) to match pandas-ta
     output if the fallback IS ever needed
  3. Loud-failure log distinguishes "columns not found" from "empty result"
     so future drift surfaces with actionable detail

Per CLAUDE.md §11 (silent-bug surfacing — fallback that diverges from
primary is a classic silent-bug class) and §14 (verification discipline:
a test that proves the bug is gone).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_close():
    """50-bar synthetic close series with controlled volatility — enough
    for a 20-period Bollinger Band to stabilize."""
    np.random.seed(42)
    return pd.DataFrame({"close": 100 + np.cumsum(np.random.randn(50) * 0.5)})


def test_compute_bollinger_bands_runs_clean_no_warning_spam(synthetic_close, caplog):
    """Primary regression: the pandas-ta path must succeed, NOT fall through
    to the warning + manual fallback. If a future pandas-ta version changes
    column naming again, the dynamic prefix match must still catch it."""
    import logging

    from backend.indicators.volatility import compute_bollinger_bands

    with caplog.at_level(logging.WARNING):
        upper, middle, lower = compute_bollinger_bands(synthetic_close, period=20, std_dev=2.0)

    # No "falling back to manual" warning should fire — the fix matches
    # columns by prefix, which works for both old and new pandas-ta naming.
    bb_warnings = [r for r in caplog.records if "Bollinger" in r.getMessage() and "fall" in r.getMessage().lower()]
    assert len(bb_warnings) == 0, (
        f"Bollinger Bands fell back to manual unexpectedly. Warnings: "
        f"{[r.getMessage() for r in bb_warnings]!r}. This is the original "
        f"bug — pandas-ta columns aren't being recognized."
    )

    # Sanity: bands have expected ordering
    valid = ~upper.isna() & ~middle.isna() & ~lower.isna()
    assert valid.sum() > 0, "all bands NaN — Bollinger computation failed"
    assert (upper[valid] >= middle[valid]).all()
    assert (middle[valid] >= lower[valid]).all()


def test_compute_bollinger_bands_handles_old_naming(synthetic_close):
    """If pandas-ta is downgraded to a version using the old BBU_20_2.0 naming,
    the prefix match must still find the columns. Simulate by patching the
    bbands return to the old format."""
    from unittest.mock import patch

    from backend.indicators.volatility import compute_bollinger_bands

    # Simulate old-format pandas-ta output
    n = len(synthetic_close)
    fake_bb_df = pd.DataFrame({
        "BBL_20_2.0": pd.Series(np.linspace(95, 99, n)),
        "BBM_20_2.0": pd.Series(np.linspace(100, 100, n)),
        "BBU_20_2.0": pd.Series(np.linspace(101, 105, n)),
    })

    with patch("backend.indicators.volatility.ta.bbands", return_value=fake_bb_df):
        upper, middle, lower = compute_bollinger_bands(synthetic_close, period=20, std_dev=2.0)

    # Should have picked up the old-format columns via prefix matching
    assert upper.iloc[-1] == 105.0
    assert middle.iloc[-1] == 100.0
    assert lower.iloc[-1] == 99.0


def test_compute_bollinger_bands_handles_new_naming(synthetic_close):
    """The CURRENT pandas-ta on this machine uses BBU_20_2.0_2.0 (std arg
    duplicated). This is the format that triggered the bug. The prefix match
    must handle it."""
    from unittest.mock import patch

    from backend.indicators.volatility import compute_bollinger_bands

    n = len(synthetic_close)
    fake_bb_df = pd.DataFrame({
        "BBL_20_2.0_2.0": pd.Series(np.linspace(94, 98, n)),
        "BBM_20_2.0_2.0": pd.Series(np.linspace(100, 100, n)),
        "BBU_20_2.0_2.0": pd.Series(np.linspace(102, 106, n)),
        "BBB_20_2.0_2.0": pd.Series(np.linspace(0.04, 0.08, n)),  # bandwidth
        "BBP_20_2.0_2.0": pd.Series(np.linspace(0.5, 0.5, n)),    # percent-b
    })

    with patch("backend.indicators.volatility.ta.bbands", return_value=fake_bb_df):
        upper, middle, lower = compute_bollinger_bands(synthetic_close, period=20, std_dev=2.0)

    assert upper.iloc[-1] == 106.0
    assert middle.iloc[-1] == 100.0
    assert lower.iloc[-1] == 98.0


def test_compute_bollinger_bands_falls_back_when_pandas_ta_returns_none(synthetic_close, caplog):
    """If pandas-ta does return None/empty, the manual fallback must fire AND
    log a warning. Verifies the fallback path still works and is loud."""
    import logging
    from unittest.mock import patch

    from backend.indicators.volatility import compute_bollinger_bands

    with patch("backend.indicators.volatility.ta.bbands", return_value=None):
        with caplog.at_level(logging.WARNING):
            upper, middle, lower = compute_bollinger_bands(synthetic_close, period=20, std_dev=2.0)

    # Manual fallback should have produced finite values
    assert upper.notna().sum() > 0
    # And the loud warning must have fired
    bb_warnings = [r for r in caplog.records if "Bollinger" in r.getMessage()]
    assert len(bb_warnings) >= 1, "expected at least one Bollinger warning on pandas-ta None return"


def test_manual_fallback_uses_population_std_not_sample(synthetic_close):
    """The manual fallback must use ddof=0 (population std) to match
    pandas-ta's behavior. Pre-fix it used pandas default ddof=1 (sample
    std), producing ~2.6% wider bands at period=20 — a silent
    divergence between primary and fallback paths."""
    from unittest.mock import patch

    from backend.indicators.volatility import compute_bollinger_bands

    # Force the fallback path
    with patch("backend.indicators.volatility.ta.bbands", return_value=None):
        upper, middle, lower = compute_bollinger_bands(synthetic_close, period=20, std_dev=2.0)

    # Compute what pandas-ta would have produced: SMA + 2 * std(ddof=0)
    expected_middle = synthetic_close["close"].rolling(window=20).mean()
    expected_std_pop = synthetic_close["close"].rolling(window=20).std(ddof=0)
    expected_upper = expected_middle + (expected_std_pop * 2.0)

    # The fallback should match the population-std computation, not the
    # sample-std (ddof=1) computation.
    valid_idx = ~upper.isna()
    np.testing.assert_allclose(
        upper[valid_idx].values, expected_upper[valid_idx].values, rtol=1e-9,
        err_msg=(
            "Manual fallback bands diverge from population-std computation. "
            "If the fallback uses ddof=1 (sample std) it will produce ~2.6% "
            "wider bands at period=20 — silent divergence from pandas-ta."
        ),
    )

    # And explicitly: the bands should NOT match the sample-std (ddof=1) shape
    expected_std_sample = synthetic_close["close"].rolling(window=20).std(ddof=1)
    expected_upper_sample = expected_middle + (expected_std_sample * 2.0)
    # The two computations should differ on at least one bar (proves ddof=0 vs ddof=1 distinction)
    assert not np.allclose(
        expected_upper[valid_idx].values, expected_upper_sample[valid_idx].values, rtol=1e-9
    ), "test fixture too small to distinguish ddof=0 from ddof=1"


def test_static_source_uses_dynamic_column_match():
    """Static check: the fix uses prefix-based dynamic matching, not exact
    column-name lookup. If a future refactor regresses to hard-coded names,
    the original bug returns and this test fails first."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] / "indicators" / "volatility.py"
    ).read_text(encoding="utf-8")

    # The fix must reference the dynamic-find helper or use startswith() over BBU/BBM/BBL
    assert "_find_col" in src or "startswith" in src, (
        "Bollinger fix uses dynamic column matching. If a refactor goes back "
        "to exact-name lookup, the pandas-ta version drift bug returns."
    )
    # And the fallback must explicitly use ddof=0
    assert "ddof=0" in src, (
        "Manual fallback must use ddof=0 to match pandas-ta's population std. "
        "Without this, primary and fallback diverge by ~2.6% on band width."
    )

"""
Test suite for Position Sizing Calculator.

Tests all sizing methods and constraint enforcement.
"""

import pytest
from backend.risk.position_sizer import PositionSizer, PositionSize


def test_position_sizer_initialization():
    """Test PositionSizer initialization with valid and invalid parameters."""
    # Valid initialization
    sizer = PositionSizer(account_balance=10000, max_position_pct=25.0, max_risk_pct=2.0)
    assert sizer.account_balance == 10000
    assert sizer.max_position_pct == 25.0
    assert sizer.max_risk_pct == 2.0

    # Invalid account balance
    with pytest.raises(ValueError, match="Account balance must be positive"):
        PositionSizer(account_balance=-1000)

    with pytest.raises(ValueError, match="Account balance must be positive"):
        PositionSizer(account_balance=0)

    # Invalid max position %
    with pytest.raises(ValueError, match="Max position % must be 0-100"):
        PositionSizer(account_balance=10000, max_position_pct=0)

    with pytest.raises(ValueError, match="Max position % must be 0-100"):
        PositionSizer(account_balance=10000, max_position_pct=150)

    # Invalid max risk %
    with pytest.raises(ValueError, match="Max risk % must be 0-100"):
        PositionSizer(account_balance=10000, max_risk_pct=0)


def test_fixed_fractional_sizing():
    """Test fixed fractional position sizing."""
    sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0, max_position_pct=100.0)

    # Standard 1% risk trade
    # Entry: $50,000, Stop: $49,000, Risk: 1%
    # Risk amount: $100, Stop distance: $1,000
    # Quantity: $100 / $1,000 = 0.1 BTC
    result = sizer.calculate_fixed_fractional(risk_pct=1.0, entry_price=50000, stop_price=49000)

    assert result.method == "fixed_fractional"
    assert result.quantity == pytest.approx(0.1, rel=1e-6)
    assert result.notional_value == pytest.approx(5000, rel=1e-6)
    assert result.risk_amount == pytest.approx(100, rel=1e-6)
    assert result.risk_percentage == pytest.approx(1.0, rel=1e-6)

    # Invalid inputs
    with pytest.raises(ValueError, match="Risk % must be"):
        sizer.calculate_fixed_fractional(risk_pct=5.0, entry_price=50000, stop_price=49000)

    with pytest.raises(ValueError, match="Entry price must be positive"):
        sizer.calculate_fixed_fractional(risk_pct=1.0, entry_price=-50000, stop_price=49000)

    with pytest.raises(ValueError, match="Entry and stop prices must be different"):
        sizer.calculate_fixed_fractional(risk_pct=1.0, entry_price=50000, stop_price=50000)


def test_fixed_fractional_with_leverage():
    """Test fixed fractional sizing with leverage."""
    sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0, max_position_pct=100.0)

    # 2x leverage - same risk, same quantity, but less margin required
    # Risk 1% = $100, Entry $50k, Stop $49k
    # Quantity = $100 / $1000 = 0.1 BTC (same as without leverage)
    # Notional = 0.1 * $50k = $5000
    # Margin required = $5000 / 2 = $2500 (50% of position value)
    result = sizer.calculate_fixed_fractional(
        risk_pct=1.0, entry_price=50000, stop_price=49000, leverage=2.0
    )

    # Quantity stays same (leverage doesn't affect risk)
    assert result.quantity == pytest.approx(0.1, rel=1e-6)
    assert result.notional_value == pytest.approx(5000, rel=1e-6)
    assert result.metadata["leverage"] == 2.0
    # Risk is still $100
    assert result.risk_amount == pytest.approx(100, rel=1e-6)


def test_kelly_criterion_sizing():
    """Test Kelly Criterion position sizing."""
    sizer = PositionSizer(account_balance=10000, max_risk_pct=5.0)

    # Win rate: 65%, Avg win: 2.5R, Avg loss: 1R
    # Kelly = (0.65 * 2.5 - 0.35) / 2.5 = 0.51 = 51%
    # Quarter Kelly = 12.75%
    # Capped at max_risk_pct = 5%
    result = sizer.calculate_kelly(
        win_rate=0.65,
        avg_win=2.5,
        avg_loss=1.0,
        entry_price=50000,
        stop_price=49000,
        kelly_fraction=0.25,
    )

    assert result.method == "kelly_criterion"
    assert result.metadata["win_rate"] == 0.65
    assert result.metadata["payoff_ratio"] == 2.5
    assert result.metadata["kelly_pct"] > 0
    assert result.risk_percentage <= 5.0  # Capped at max

    # Invalid inputs
    with pytest.raises(ValueError, match="Win rate must be 0-1"):
        sizer.calculate_kelly(
            win_rate=1.5, avg_win=2.0, avg_loss=1.0, entry_price=50000, stop_price=49000
        )

    with pytest.raises(ValueError, match="Average win must be positive"):
        sizer.calculate_kelly(
            win_rate=0.65, avg_win=-2.0, avg_loss=1.0, entry_price=50000, stop_price=49000
        )


def test_atr_based_sizing():
    """Test ATR-based position sizing."""
    sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0)

    # ATR: 1500, Multiplier: 2.0, Entry: 50000
    # Stop distance = 1500 * 2.0 = 3000
    # Stop price = 50000 - 3000 = 47000
    result = sizer.calculate_atr_based(
        atr=1500, atr_multiplier=2.0, entry_price=50000, risk_pct=1.0
    )

    assert result.method == "atr_based"
    assert result.metadata["atr"] == 1500
    assert result.metadata["atr_multiplier"] == 2.0
    assert result.metadata["stop_distance_atr"] == 2.0

    # Invalid inputs
    with pytest.raises(ValueError, match="ATR must be positive"):
        sizer.calculate_atr_based(atr=-100, atr_multiplier=2.0, entry_price=50000)

    with pytest.raises(ValueError, match="ATR multiplier must be positive"):
        sizer.calculate_atr_based(atr=1500, atr_multiplier=0, entry_price=50000)


def test_fixed_dollar_risk_sizing():
    """Test fixed dollar risk position sizing."""
    sizer = PositionSizer(account_balance=10000, max_risk_pct=5.0, max_position_pct=100.0)

    # Risk $100, Entry: $50,000, Stop: $49,000
    # Stop distance: $1,000
    # Quantity: $100 / $1,000 = 0.1 BTC
    result = sizer.calculate_fixed_dollar_risk(risk_amount=100, entry_price=50000, stop_price=49000)

    assert result.method == "fixed_dollar_risk"
    assert result.quantity == pytest.approx(0.1, rel=1e-6)
    assert result.risk_amount == pytest.approx(100, rel=1e-6)
    assert result.metadata["target_risk_amount"] == 100

    # Invalid inputs
    with pytest.raises(ValueError, match="Risk amount must be positive"):
        sizer.calculate_fixed_dollar_risk(risk_amount=-100, entry_price=50000, stop_price=49000)

    with pytest.raises(ValueError, match="exceeds account balance"):
        sizer.calculate_fixed_dollar_risk(risk_amount=20000, entry_price=50000, stop_price=49000)


def test_minimum_order_value_constraint():
    """Test minimum order value constraint enforcement."""
    sizer = PositionSizer(account_balance=10000, min_order_value=10.0)

    # Tiny position that would be < $10
    # Risk 0.01%, Entry $50,000, Stop $49,000
    # Risk amount: $1, Quantity: 0.001 BTC, Value: $50
    # Should be scaled up to meet minimum
    result = sizer.calculate_fixed_fractional(risk_pct=0.01, entry_price=50000, stop_price=49000)

    # Notional value should be >= min order value
    assert result.notional_value >= sizer.min_order_value


def test_maximum_position_size_constraint():
    """Test maximum position size constraint enforcement."""
    sizer = PositionSizer(account_balance=10000, max_position_pct=10.0, max_risk_pct=10.0)

    # Try to take huge position (risk 5%)
    # Entry $1000, Stop $900, Risk 5% = $500
    # Stop distance $100, Quantity: 5 units, Value: $5000
    # But max position = $1000 (10% of $10k)
    result = sizer.calculate_fixed_fractional(
        risk_pct=5.0, entry_price=1000, stop_price=900, leverage=1.0
    )

    # Position should be capped
    max_allowed = sizer.account_balance * (sizer.max_position_pct / 100)
    assert result.notional_value <= max_allowed


def test_update_balance():
    """Test account balance updates."""
    sizer = PositionSizer(account_balance=10000)

    # Update balance
    sizer.update_balance(12000)
    assert sizer.account_balance == 12000

    # Invalid balance
    with pytest.raises(ValueError, match="cannot be negative"):
        sizer.update_balance(-1000)


def test_max_values_getters():
    """Test max position and risk value getters."""
    sizer = PositionSizer(account_balance=10000, max_position_pct=25.0, max_risk_pct=2.0)

    assert sizer.get_max_position_value() == 2500  # 25% of 10k
    assert sizer.get_max_risk_value() == 200  # 2% of 10k


def test_validate_position_size():
    """Test position size validation."""
    sizer = PositionSizer(
        account_balance=10000, max_position_pct=25.0, max_risk_pct=2.0, min_order_value=10.0
    )

    # Valid position (within 25% max position = $2500)
    # 0.04 BTC * $50,000 = $2000 (20% of account)
    is_valid, reason = sizer.validate_position_size(
        quantity=0.04, entry_price=50000, stop_price=49000
    )
    assert is_valid
    assert reason == "Position size valid"

    # Position too small
    is_valid, reason = sizer.validate_position_size(
        quantity=0.0001, entry_price=50000, stop_price=49000
    )
    assert not is_valid
    assert "below minimum" in reason

    # Position too large
    is_valid, reason = sizer.validate_position_size(
        quantity=1.0, entry_price=50000, stop_price=49000
    )
    assert not is_valid
    assert "exceeds max" in reason


def test_position_size_dataclass():
    """Test PositionSize dataclass validation."""
    # Valid position size
    pos = PositionSize(
        quantity=0.1,
        notional_value=5000,
        risk_amount=100,
        risk_percentage=1.0,
        position_percentage=50.0,
        method="fixed_fractional",
        metadata={},
    )
    assert pos.quantity == 0.1

    # Invalid quantity
    with pytest.raises(ValueError, match="quantity must be"):
        PositionSize(
            quantity=-0.1,
            notional_value=5000,
            risk_amount=100,
            risk_percentage=1.0,
            position_percentage=50.0,
            method="test",
            metadata={},
        )

    # Invalid risk percentage
    with pytest.raises(ValueError, match="Risk percentage must be 0-100"):
        PositionSize(
            quantity=0.1,
            notional_value=5000,
            risk_amount=100,
            risk_percentage=150,
            position_percentage=50.0,
            method="test",
            metadata={},
        )


def test_short_position_sizing():
    """Test position sizing for short trades."""
    sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0, max_position_pct=100.0)

    # Short: Entry $50,000, Stop $51,000 (above entry)
    # Risk 1% = $100, Stop distance $1,000
    # Quantity: 0.1 BTC
    result = sizer.calculate_fixed_fractional(risk_pct=1.0, entry_price=50000, stop_price=51000)

    # Should work same as long (absolute stop distance)
    assert result.quantity == pytest.approx(0.1, rel=1e-6)
    assert result.risk_amount == pytest.approx(100, rel=1e-6)


def test_realistic_btc_trade():
    """Test realistic BTC trade scenario."""
    # $10k account, 1% risk, BTC at $50k
    sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0, max_position_pct=100.0)

    # Long from $50,000, stop at $48,500 (3% stop, ~1.5 ATR)
    # Risk 1% = $100
    # Stop distance = $1,500
    # Quantity = $100 / $1,500 = 0.0667 BTC
    # Position value = 0.0667 * $50,000 = $3,333
    result = sizer.calculate_fixed_fractional(risk_pct=1.0, entry_price=50000, stop_price=48500)

    assert result.quantity == pytest.approx(0.0667, rel=1e-3)
    assert result.notional_value == pytest.approx(3333, rel=1e-1)
    assert result.risk_amount == pytest.approx(100, rel=1e-1)
    assert result.position_percentage == pytest.approx(33.33, rel=1e-1)


def test_realistic_futures_trade_with_leverage():
    """Test realistic futures trade with 5x leverage."""
    # $5k account, 2% risk, BTC futures 5x leverage
    # With leverage, margin constraint will apply
    sizer = PositionSizer(account_balance=5000, max_risk_pct=3.0, max_position_pct=100.0)

    # Entry $60,000, Stop $59,400 (1% stop = $600)
    # Risk 2% = $100
    # Quantity = $100 / $600 = 0.1667 BTC
    # Notional = 0.1667 * $60,000 = $10,000
    # Margin required with 5x leverage = $10,000 / 5 = $2,000 (40% of account)
    # But max position (notional) = $5,000 (100% of account)
    # So position is capped by max_position_pct
    result = sizer.calculate_fixed_fractional(
        risk_pct=2.0, entry_price=60000, stop_price=59400, leverage=5.0
    )

    # Position will be capped at max_position_pct = 100% = $5000
    # Quantity = $5000 / $60,000 = 0.0833 BTC
    assert result.quantity == pytest.approx(0.0833, rel=1e-3)
    assert result.notional_value == pytest.approx(5000, rel=1e-1)
    assert result.metadata["leverage"] == 5.0

    # Risk will be less than target due to position cap
    # Risk = 0.0833 * $600 = $50 (1% instead of 2%)
    assert result.risk_amount == pytest.approx(50, rel=1e-1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

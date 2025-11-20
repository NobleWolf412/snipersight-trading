"""
Test suite for Risk Manager.

Tests portfolio-level risk controls and compliance validation.
"""

import pytest
from datetime import datetime, timedelta
from backend.risk.risk_manager import RiskManager, Position, Trade, RiskCheck


def test_risk_manager_initialization():
    """Test RiskManager initialization with valid and invalid parameters."""
    # Valid initialization
    rm = RiskManager(
        account_balance=10000,
        max_open_positions=5,
        max_asset_exposure_pct=20.0
    )
    assert rm.account_balance == 10000
    assert rm.max_open_positions == 5
    assert rm.max_asset_exposure_pct == 20.0
    
    # Invalid account balance
    with pytest.raises(ValueError, match="Account balance must be positive"):
        RiskManager(account_balance=0)
    
    with pytest.raises(ValueError, match="Account balance must be positive"):
        RiskManager(account_balance=-1000)
    
    # Invalid max positions
    with pytest.raises(ValueError, match="Max open positions must be"):
        RiskManager(account_balance=10000, max_open_positions=0)
    
    # Invalid exposure %
    with pytest.raises(ValueError, match="Max asset exposure must be"):
        RiskManager(account_balance=10000, max_asset_exposure_pct=0)
    
    with pytest.raises(ValueError, match="Max asset exposure must be"):
        RiskManager(account_balance=10000, max_asset_exposure_pct=150)


def test_validate_new_trade_max_positions():
    """Test max open positions limit."""
    rm = RiskManager(account_balance=10000, max_open_positions=2)
    
    # First trade - should pass
    check = rm.validate_new_trade(
        symbol="BTC/USDT",
        direction="LONG",
        position_value=2000,
        risk_amount=100
    )
    assert check.passed
    
    # Add position
    rm.add_position("BTC/USDT", "LONG", 0.04, 50000)
    
    # Second trade - should pass
    check = rm.validate_new_trade(
        symbol="ETH/USDT",
        direction="LONG",
        position_value=1500,
        risk_amount=75
    )
    assert check.passed
    
    # Add second position
    rm.add_position("ETH/USDT", "LONG", 0.5, 3000)
    
    # Third trade - should fail (max 2 positions)
    check = rm.validate_new_trade(
        symbol="SOL/USDT",
        direction="LONG",
        position_value=1000,
        risk_amount=50
    )
    assert not check.passed
    assert "Max open positions" in check.reason
    assert 'max_open_positions' in check.limits_hit


def test_validate_new_trade_asset_exposure():
    """Test asset exposure limit."""
    rm = RiskManager(
        account_balance=10000,
        max_asset_exposure_pct=20.0  # Max $2000 per asset
    )
    
    # Trade within limit - should pass
    check = rm.validate_new_trade(
        symbol="BTC/USDT",
        direction="LONG",
        position_value=1500,
        risk_amount=75
    )
    assert check.passed
    
    # Trade exceeding limit - should fail
    check = rm.validate_new_trade(
        symbol="BTC/USDT",
        direction="LONG",
        position_value=2500,  # > 20% of $10k
        risk_amount=100
    )
    assert not check.passed
    assert "Asset exposure limit exceeded" in check.reason
    assert 'asset_exposure' in check.limits_hit


def test_validate_new_trade_daily_loss_limit():
    """Test daily loss limit enforcement."""
    rm = RiskManager(
        account_balance=10000,
        max_daily_loss_pct=5.0  # Max $500 daily loss
    )
    
    # Simulate losses
    # Loss 1: -$200
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000, 48000)
    rm.close_position("BTC/USDT", 48000)  # -$200 loss
    
    # Loss 2: -$250
    rm.add_position("ETH/USDT", "LONG", 1.0, 3000, 2750)
    rm.close_position("ETH/USDT", 2750)  # -$250 loss
    
    # Total daily loss now -$450, limit is $500
    
    # New trade should still pass (under limit)
    check = rm.validate_new_trade(
        symbol="SOL/USDT",
        direction="LONG",
        position_value=1000,
        risk_amount=40
    )
    assert check.passed
    
    # Simulate one more loss pushing over limit
    rm.add_position("SOL/USDT", "LONG", 10, 100, 95)
    rm.close_position("SOL/USDT", 95)  # -$50 loss
    
    # Total daily loss now -$500, hit limit
    check = rm.validate_new_trade(
        symbol="MATIC/USDT",
        direction="LONG",
        position_value=500,
        risk_amount=25
    )
    assert not check.passed
    assert "Daily loss limit hit" in check.reason
    assert 'daily_loss_limit' in check.limits_hit


def test_validate_new_trade_position_concentration():
    """Test position concentration limit."""
    rm = RiskManager(
        account_balance=10000,
        max_position_concentration_pct=25.0,  # Max $2500 per position
        max_asset_exposure_pct=50.0  # Higher to avoid hitting asset limit first
    )
    
    # Position within limit
    check = rm.validate_new_trade(
        symbol="BTC/USDT",
        direction="LONG",
        position_value=2000,
        risk_amount=100
    )
    assert check.passed
    
    # Position too large
    check = rm.validate_new_trade(
        symbol="BTC/USDT",
        direction="LONG",
        position_value=3000,  # > 25% of account
        risk_amount=100
    )
    assert not check.passed
    assert "Position too large" in check.reason
    assert 'position_concentration' in check.limits_hit


def test_add_and_update_position():
    """Test adding and updating positions."""
    rm = RiskManager(account_balance=10000)
    
    # Add position
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000, 50000)
    
    assert "BTC/USDT" in rm.positions
    assert rm.positions["BTC/USDT"].quantity == 0.1
    assert rm.positions["BTC/USDT"].entry_price == 50000
    assert rm.positions["BTC/USDT"].unrealized_pnl == 0.0
    
    # Update with profit
    rm.update_position("BTC/USDT", 51000)
    assert rm.positions["BTC/USDT"].current_price == 51000
    assert rm.positions["BTC/USDT"].unrealized_pnl == pytest.approx(100, rel=1e-6)  # 0.1 * $1000
    
    # Update with loss
    rm.update_position("BTC/USDT", 49000)
    assert rm.positions["BTC/USDT"].unrealized_pnl == pytest.approx(-100, rel=1e-6)


def test_close_position():
    """Test closing positions and recording trades."""
    rm = RiskManager(account_balance=10000)
    
    # Add and close with profit
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000)
    trade = rm.close_position("BTC/USDT", 51000)
    
    assert trade.symbol == "BTC/USDT"
    assert trade.pnl == pytest.approx(100, rel=1e-6)  # 0.1 * $1000 profit
    assert "BTC/USDT" not in rm.positions
    assert rm.account_balance == pytest.approx(10100, rel=1e-6)
    assert len(rm.trade_history) == 1
    
    # Add and close with loss
    rm.add_position("ETH/USDT", "SHORT", 1.0, 3000)
    trade = rm.close_position("ETH/USDT", 3100)
    
    assert trade.pnl == pytest.approx(-100, rel=1e-6)  # Short lost $100
    assert rm.account_balance == pytest.approx(10000, rel=1e-6)  # Back to starting


def test_position_pnl_calculation():
    """Test PnL calculation for long and short positions."""
    # Long position
    pos_long = Position(
        symbol="BTC/USDT",
        direction="LONG",
        quantity=0.1,
        entry_price=50000,
        current_price=51000,
        unrealized_pnl=100
    )
    
    assert pos_long.notional_value == pytest.approx(5100, rel=1e-6)
    assert pos_long.pnl_pct == pytest.approx(2.0, rel=1e-6)  # 2% gain
    
    # Short position
    pos_short = Position(
        symbol="ETH/USDT",
        direction="SHORT",
        quantity=1.0,
        entry_price=3000,
        current_price=2900,
        unrealized_pnl=100
    )
    
    assert pos_short.pnl_pct == pytest.approx(3.33, rel=1e-2)  # 3.33% gain


def test_get_total_exposure():
    """Test total exposure calculation."""
    rm = RiskManager(account_balance=10000)
    
    # No positions
    assert rm.get_total_exposure() == 0.0
    
    # Add positions
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000, 50000)  # $5000
    rm.add_position("ETH/USDT", "LONG", 1.0, 3000, 3000)    # $3000
    
    assert rm.get_total_exposure() == pytest.approx(8000, rel=1e-6)


def test_get_unrealized_pnl():
    """Test unrealized PnL calculation."""
    rm = RiskManager(account_balance=10000)
    
    # Add positions
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000, 51000)  # +$100
    rm.add_position("ETH/USDT", "LONG", 1.0, 3000, 2900)    # -$100
    
    # Update unrealized PnL
    rm.update_position("BTC/USDT", 51000)
    rm.update_position("ETH/USDT", 2900)
    
    assert rm.get_unrealized_pnl() == pytest.approx(0, rel=1e-6)  # +100 - 100


def test_get_equity():
    """Test equity calculation (balance + unrealized PnL)."""
    rm = RiskManager(account_balance=10000)
    
    # No positions
    assert rm.get_equity() == 10000
    
    # Add winning position
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000, 51000)
    rm.update_position("BTC/USDT", 51000)
    
    assert rm.get_equity() == pytest.approx(10100, rel=1e-6)


def test_get_drawdown():
    """Test drawdown calculation."""
    rm = RiskManager(account_balance=10000)
    
    # No drawdown initially
    assert rm.get_drawdown() == 0.0
    
    # Add losing position
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000, 48000)
    rm.update_position("BTC/USDT", 48000)  # -$200 unrealized
    
    # Drawdown = 200 / 10000 = 2%
    assert rm.get_drawdown() == pytest.approx(2.0, rel=1e-6)


def test_get_position_count_and_direction():
    """Test position counting methods."""
    rm = RiskManager(account_balance=10000)
    
    assert rm.get_position_count() == 0
    
    # Add mixed positions
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000)
    rm.add_position("ETH/USDT", "SHORT", 1.0, 3000)
    rm.add_position("SOL/USDT", "LONG", 10, 100)
    
    assert rm.get_position_count() == 3
    
    counts = rm.get_positions_by_direction()
    assert counts['LONG'] == 2
    assert counts['SHORT'] == 1


def test_correlated_exposure():
    """Test correlated asset exposure calculation."""
    rm = RiskManager(
        account_balance=10000,
        max_correlated_exposure_pct=30.0  # Max $3000 in correlated assets
    )
    
    # Add BTC position
    rm.add_position("BTC/USDT", "LONG", 0.04, 50000)  # $2000
    
    # Try to add more BTC exposure (correlated)
    # Total would be $2000 + $1500 = $3500 > $3000 limit
    check = rm.validate_new_trade(
        symbol="BTC/USD",  # Correlated with BTC/USDT
        direction="LONG",
        position_value=1500,
        risk_amount=75
    )
    assert not check.passed
    assert "Correlated exposure" in check.reason


def test_risk_summary():
    """Test comprehensive risk summary."""
    rm = RiskManager(account_balance=10000)
    
    # Add positions
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000, 51000)
    rm.add_position("ETH/USDT", "SHORT", 1.0, 3000, 2900)
    
    rm.update_position("BTC/USDT", 51000)  # +$100
    rm.update_position("ETH/USDT", 2900)   # +$100
    
    summary = rm.get_risk_summary()
    
    assert summary['account_balance'] == 10000
    assert summary['equity'] == pytest.approx(10200, rel=1e-6)
    assert summary['unrealized_pnl'] == pytest.approx(200, rel=1e-6)
    assert summary['open_positions'] == 2
    assert summary['max_positions'] == 5
    assert summary['positions_by_direction']['LONG'] == 1
    assert summary['positions_by_direction']['SHORT'] == 1


def test_weekly_loss_limit():
    """Test weekly loss limit enforcement."""
    rm = RiskManager(
        account_balance=10000,
        max_daily_loss_pct=15.0,  # High enough to not hit daily limit
        max_weekly_loss_pct=10.0  # Max $1000 weekly loss
    )
    
    # Simulate losses over several days
    for i in range(5):
        rm.add_position(f"COIN{i}/USDT", "LONG", 1.0, 1000, 800)
        trade = rm.close_position(f"COIN{i}/USDT", 800)  # -$200 each
    
    # Total weekly loss: -$1000, hit limit
    check = rm.validate_new_trade(
        symbol="BTC/USDT",
        direction="LONG",
        position_value=1000,
        risk_amount=50
    )
    assert not check.passed
    assert "Weekly loss limit hit" in check.reason
    assert 'weekly_loss_limit' in check.limits_hit


def test_replace_existing_position():
    """Test that replacing existing position doesn't trigger max positions limit."""
    rm = RiskManager(account_balance=10000, max_open_positions=1)
    
    # Add first position
    rm.add_position("BTC/USDT", "LONG", 0.1, 50000)
    
    # Close it
    rm.close_position("BTC/USDT", 51000)
    
    # Should be able to add again (position slot freed)
    check = rm.validate_new_trade(
        symbol="BTC/USDT",
        direction="SHORT",
        position_value=2000,
        risk_amount=100
    )
    assert check.passed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

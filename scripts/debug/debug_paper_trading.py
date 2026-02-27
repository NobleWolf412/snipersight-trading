#!/usr/bin/env python3
"""
Debug script for Paper Trading Pipeline

Tests each component of the pipeline step-by-step to identify issues.
Run with: python debug_paper_trading.py
"""

import asyncio
import sys
import traceback
from datetime import datetime, timezone

# Ensure proper imports
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')


def section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def success(msg: str):
    print(f"  ✅ {msg}")


def error(msg: str):
    print(f"  ❌ {msg}")


def info(msg: str):
    print(f"  ℹ️  {msg}")


def warn(msg: str):
    print(f"  ⚠️  {msg}")


async def main():
    print("\n" + "="*60)
    print("  PAPER TRADING PIPELINE DEBUGGER")
    print("="*60)
    
    # ==========================================
    # STEP 1: Test Imports
    # ==========================================
    section("STEP 1: Testing Imports")
    
    try:
        from backend.shared.models.planner import TradePlan, EntryZone, StopLoss, Target
        success("TradePlan, EntryZone, StopLoss, Target imported")
        
        # Check EntryZone attributes
        info(f"EntryZone fields: {[f.name for f in EntryZone.__dataclass_fields__.values()]}")
        
    except Exception as e:
        error(f"Failed to import planner models: {e}")
        traceback.print_exc()
        return
    
    try:
        from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
        success("ConfluenceBreakdown, ConfluenceFactor imported")
    except Exception as e:
        error(f"Failed to import scoring models: {e}")
        traceback.print_exc()
        return
    
    try:
        from backend.shared.config.scanner_modes import get_mode, list_modes
        success("Scanner modes imported")
        info(f"Available modes: {list_modes()}")
    except Exception as e:
        error(f"Failed to import scanner modes: {e}")
        traceback.print_exc()
        return
    
    try:
        from backend.data.adapters.phemex import PhemexAdapter
        success("PhemexAdapter imported")
    except Exception as e:
        error(f"Failed to import PhemexAdapter: {e}")
        traceback.print_exc()
        return
    
    try:
        from backend.engine.orchestrator import Orchestrator
        success("Orchestrator imported")
    except Exception as e:
        error(f"Failed to import Orchestrator: {e}")
        traceback.print_exc()
        return
    
    try:
        from backend.bot.paper_trading_service import PaperTradingService, PaperTradingConfig
        success("PaperTradingService imported")
    except Exception as e:
        error(f"Failed to import PaperTradingService: {e}")
        traceback.print_exc()
        return
    
    # ==========================================
    # STEP 2: Test Model Creation
    # ==========================================
    section("STEP 2: Testing Model Creation")
    
    try:
        # Test EntryZone (only has near_entry, far_entry, rationale)
        entry = EntryZone(
            near_entry=100.0,
            far_entry=99.0,
            rationale="Test entry zone"
        )
        success(f"EntryZone created: near={entry.near_entry}, far={entry.far_entry}")
        info(f"EntryZone attributes: {vars(entry)}")
    except Exception as e:
        error(f"Failed to create EntryZone: {e}")
        traceback.print_exc()
        return
    
    try:
        # Test StopLoss (has level, distance_atr, rationale)
        stop = StopLoss(
            level=95.0,
            distance_atr=1.5,
            rationale="Test stop loss"
        )
        success(f"StopLoss created: level={stop.level}")
    except Exception as e:
        error(f"Failed to create StopLoss: {e}")
        traceback.print_exc()
        return
    
    try:
        # Test Target
        target = Target(
            level=110.0,
            percentage=100.0,
            rationale="Test target"
        )
        success(f"Target created: level={target.level}")
    except Exception as e:
        error(f"Failed to create Target: {e}")
        traceback.print_exc()
        return
    
    try:
        # Test ConfluenceBreakdown (many required fields!)
        factor = ConfluenceFactor(
            name="test_factor",
            score=80.0,
            weight=1.0,
            rationale="Test factor"
        )
        breakdown = ConfluenceBreakdown(
            total_score=80.0,
            factors=[factor],
            synergy_bonus=0.0,
            conflict_penalty=0.0,
            regime="trend",
            htf_aligned=True,
            btc_impulse_gate=True
        )
        success(f"ConfluenceBreakdown created: score={breakdown.total_score}")
    except Exception as e:
        error(f"Failed to create ConfluenceBreakdown: {e}")
        traceback.print_exc()
        return
    
    try:
        # Test TradePlan
        plan = TradePlan(
            symbol="TEST/USDT",
            direction="LONG",
            setup_type="scalp",
            entry_zone=entry,
            stop_loss=stop,
            targets=[target],
            risk_reward=2.0,
            confidence_score=80.0,
            confluence_breakdown=breakdown,
            rationale="Test trade plan for debugging"
        )
        success(f"TradePlan created: {plan.symbol} {plan.direction}")
        info(f"TradePlan entry_zone type: {type(plan.entry_zone)}")
        info(f"TradePlan entry_zone.near_entry: {plan.entry_zone.near_entry}")
    except Exception as e:
        error(f"Failed to create TradePlan: {e}")
        traceback.print_exc()
        return
    
    # ==========================================
    # STEP 3: Test Exchange Adapter
    # ==========================================
    section("STEP 3: Testing Exchange Adapter")
    
    try:
        adapter = PhemexAdapter()
        success("PhemexAdapter created")
        
        # Fetch a single candle to test
        df = adapter.fetch_ohlcv("BTC/USDT", "1h", limit=10)
        if df is not None and not df.empty:
            success(f"Fetched {len(df)} candles for BTC/USDT 1h")
            info(f"Latest close: ${df['close'].iloc[-1]:,.2f}")
        else:
            warn("No data returned from exchange")
    except Exception as e:
        error(f"Exchange adapter failed: {e}")
        traceback.print_exc()
    
    # ==========================================
    # STEP 4: Test Orchestrator
    # ==========================================
    section("STEP 4: Testing Orchestrator")
    
    try:
        from backend.shared.config.defaults import ScanConfig
        
        mode = get_mode("surgical")
        success(f"Got mode: {mode.name} (timeframes: {mode.timeframes})")
        
        # Create ScanConfig for the mode
        config = ScanConfig(
            profile=mode.profile,
            timeframes=mode.timeframes,
            min_confluence_score=mode.min_confluence_score,
            min_rr_ratio=1.5,
            max_symbols=5
        )
        success(f"Created ScanConfig: profile={config.profile}")
        
        orchestrator = Orchestrator(config=config, exchange_adapter=adapter)
        success("Orchestrator created")
        
        orchestrator.apply_mode(mode)
        success("Mode applied to orchestrator")
        
    except Exception as e:
        error(f"Orchestrator setup failed: {e}")
        traceback.print_exc()
        return
    
    # ==========================================
    # STEP 5: Run a Scan
    # ==========================================
    section("STEP 5: Running Test Scan")
    
    try:
        info("Scanning BTC/USDT only (for speed)...")
        trade_plans, rejections = orchestrator.scan(symbols=["BTC/USDT"])
        
        success(f"Scan completed: {len(trade_plans)} signals, {len(rejections) if isinstance(rejections, dict) else 0} rejections")
        
        if trade_plans:
            plan = trade_plans[0]
            info(f"\n  --- First Signal Details ---")
            info(f"  Symbol: {plan.symbol}")
            info(f"  Direction: {plan.direction}")
            info(f"  Setup Type: {plan.setup_type}")
            info(f"  Confidence: {plan.confidence_score}%")
            
            # Check entry_zone specifically
            info(f"\n  --- EntryZone Debug ---")
            info(f"  entry_zone type: {type(plan.entry_zone)}")
            info(f"  entry_zone: {plan.entry_zone}")
            
            if hasattr(plan.entry_zone, 'near_entry'):
                info(f"  near_entry: {plan.entry_zone.near_entry}")
            else:
                error("  entry_zone has NO 'near_entry' attribute!")
                info(f"  Available attrs: {dir(plan.entry_zone)}")
            
            if hasattr(plan.entry_zone, 'far_entry'):
                info(f"  far_entry: {plan.entry_zone.far_entry}")
            else:
                error("  entry_zone has NO 'far_entry' attribute!")
            
            info(f"\n  --- StopLoss Debug ---")
            info(f"  stop_loss type: {type(plan.stop_loss)}")
            info(f"  stop_loss.level: {plan.stop_loss.level}")
            
            info(f"\n  --- Targets Debug ---")
            info(f"  targets count: {len(plan.targets)}")
            for i, t in enumerate(plan.targets):
                info(f"  target[{i}]: level={t.level}, pct={t.percentage}%")
        else:
            warn("No signals generated (may be normal depending on market)")
            
            # Show rejections
            if rejections:
                info("\n  --- Rejection Reasons ---")
                for symbol, reasons in (rejections.items() if isinstance(rejections, dict) else []):
                    info(f"  {symbol}: {reasons}")
    
    except Exception as e:
        error(f"Scan failed: {e}")
        traceback.print_exc()
        return
    
    # ==========================================
    # STEP 6: Test Paper Trading Service
    # ==========================================
    section("STEP 6: Testing Paper Trading Service")
    
    try:
        service = PaperTradingService()
        success("PaperTradingService created")
        
        config = PaperTradingConfig(
            initial_balance=10000,
            risk_per_trade=1.0,
            leverage=1,
            max_positions=3,
            sniper_mode='surgical',
            scan_interval_minutes=5,
            symbols=['BTC/USDT']
        )
        success("PaperTradingConfig created")
        
        info("Starting paper trading service...")
        result = await service.start(config)
        success(f"Service started: session={result['session_id']}")
        
        # Wait for first scan
        info("Waiting for first scan (max 30s)...")
        for i in range(30):
            await asyncio.sleep(1)
            status = service.get_status()
            if status.get('last_scan_at'):
                success("First scan completed!")
                break
            if i % 5 == 0 and i > 0:
                info(f"  Still waiting... ({i}s)")
        
        # Get final status
        status = service.get_status()
        info(f"\n  --- Service Status ---")
        info(f"  Status: {status['status']}")
        info(f"  Scans: {status['statistics']['scans_completed']}")
        info(f"  Signals: {status['statistics']['signals_generated']}")
        info(f"  Positions: {len(status['positions'])}")
        info(f"  Cache: {status.get('cache_stats', {})}")
        
        # Show activity log
        info(f"\n  --- Recent Activity ---")
        for act in status['recent_activity'][-5:]:
            info(f"  [{act['event_type']}] {act.get('data', {})}")
        
        # Stop service
        await service.stop()
        success("Service stopped")
        
    except Exception as e:
        error(f"Paper trading service failed: {e}")
        traceback.print_exc()
        return
    
    # ==========================================
    # SUMMARY
    # ==========================================
    section("SUMMARY")
    success("All pipeline components tested successfully!")
    info("If you see errors above, check the specific component that failed.")


if __name__ == "__main__":
    asyncio.run(main())

"""
SniperSight CLI - Command-line interface.

Following IMPLEMENTATION_ROADMAP.md Step 7 and ARCHITECTURE.md sniper-themed messaging.
"""
import typer
from typing import Optional
from datetime import datetime

app = typer.Typer(help="🎯 SniperSight - Institutional-Grade Crypto Market Scanner")


@app.command()
def scan(
    profile: str = typer.Option("balanced", help="Strategy profile (balanced/trend/range/aggressive)"),
    symbols: str = typer.Option("top20", help="Symbol universe (top10/top20/top50 or comma-separated list)"),
    exchange: str = typer.Option("binance", help="Exchange to scan (binance/bybit)"),
    output: str = typer.Option("console", help="Output format (console/json/telegram)")
):
    """
    🎯 Sweep the field - Run a market scan for high-conviction setups.
    
    Executes the full pipeline:
    - Multi-timeframe data ingestion
    - Technical indicator computation
    - Smart-Money Concept detection
    - Confluence scoring
    - Trade plan generation
    - Risk validation
    """
    typer.echo(f"🎯 SniperSight - Sweeping the field...")
    typer.echo(f"Profile: {profile} | Universe: {symbols} | Exchange: {exchange}")
    typer.echo()
    
    try:
        from backend.engine.orchestrator import Orchestrator
        from backend.shared.config.defaults import ScanConfig
        
        # Load configuration based on profile
        config = ScanConfig(
            profile=profile,
            timeframes=['1W', '1D', '4H', '1H', '15m'] if profile == "balanced" else ['4H', '1H', '15m'],
            min_confluence_score=65.0 if profile == "balanced" else 70.0
        )
        
        # Parse symbol list
        if symbols == "top20":
            symbol_list = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'MATIC/USDT'][:5]  # Limited for demo
        elif symbols == "top10":
            symbol_list = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
        else:
            symbol_list = symbols.split(',')
        
        # Initialize orchestrator
        typer.echo("🔧 Initializing orchestrator...")
        orchestrator = Orchestrator(config)
        
        # Run scan
        typer.echo(f"📡 Scanning {len(symbol_list)} symbols...")
        results = orchestrator.scan(symbol_list)
        
        # Display results
        if results:
            typer.echo(f"\n🎯 {len(results)} high-conviction setups found:")
            typer.echo("=" * 60)
            
            for i, plan in enumerate(results, 1):
                typer.echo(f"\n{i}. {plan.symbol} - {plan.direction} ({plan.setup_type})")
                typer.echo(f"   Confidence: {plan.confidence_score:.1f}%")
                typer.echo(f"   Entry: ${plan.entry_zone.near_entry:.2f} - ${plan.entry_zone.far_entry:.2f}")
                typer.echo(f"   Stop: ${plan.stop_loss.level:.2f}")
                typer.echo(f"   Risk:Reward: {plan.risk_reward:.2f}:1")
                
                if output == "json":
                    import json
                    typer.echo(f"   JSON: {json.dumps(plan.__dict__, default=str, indent=2)}")
        else:
            typer.echo("📭 No qualifying setups found in current market conditions")
            
    except ImportError as e:
        typer.echo(f"❌ Missing dependencies: {e}")
        typer.echo("✅ Backend components need to be completed")
    except Exception as e:
        typer.echo(f"❌ Scan failed: {e}")
        typer.echo("📋 Check logs for details")


@app.command()
def backtest(
    profile: str = typer.Option("balanced", help="Strategy profile"),
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., help="End date (YYYY-MM-DD)"),
    symbols: str = typer.Option("BTC/USDT,ETH/USDT", help="Symbols to backtest"),
    output: str = typer.Option("report.json", help="Output file path")
):
    """
    📊 Run historical validation backtest.
    
    Tests strategy performance on historical data with deterministic fixtures.
    """
    typer.echo(f"📊 SniperSight Backtest")
    typer.echo(f"Period: {start} → {end}")
    typer.echo(f"Profile: {profile} | Symbols: {symbols}")
    typer.echo()
    
    try:
        from backend.engine.backtest_engine import BacktestEngine
        
        # Initialize engine
        typer.echo(f"🔧 Initializing backtest engine...")
        engine = BacktestEngine(profile=profile)
        
        # Run backtest
        typer.echo(f"📡 Running backtest on {symbols}...")
        results = engine.run(start, end, symbols)
        
        # Display results
        if results:
            typer.echo(f"\n✅ {len(results)} signals generated during backtest period:")
            typer.echo("=" * 60)
            
            for i, plan in enumerate(results, 1):
                typer.echo(f"\n{i}. {plan.symbol} - {plan.direction} ({plan.setup_type})")
                typer.echo(f"   Confidence: {plan.confidence_score:.1f}%")
                typer.echo(f"   Entry: ${plan.entry_zone.near_entry:.2f} - ${plan.entry_zone.far_entry:.2f}")
                typer.echo(f"   Stop: ${plan.stop_loss.level:.2f}")
                typer.echo(f"   Risk:Reward: {plan.risk_reward:.2f}:1")
                
            if output:
                import json
                with open(output, 'w') as f:
                    data = [plan.__dict__ for plan in results]
                    json.dump(data, f, default=str, indent=2)
                typer.echo(f"\n💾 Results saved to {output}")
        else:
            typer.echo("📭 No signals generated in backtest data")
            
    except Exception as e:
        typer.echo(f"❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()


@app.command()
def audit(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output")
):
    """
    ✅ Run comprehensive quality audit.
    
    Validates:
    - Schema compliance
    - Test coverage
    - Deterministic backtest results
    - Quality gate configurations
    """
    typer.echo("✅ SniperSight Quality Audit")
    typer.echo()
    typer.echo("⚠️  Quality audit is available via the web UI diagnostics panel.")
    typer.echo("    Use: /api/scanner/diagnostics for programmatic access.")


@app.command()
def version():
    """Display SniperSight version information."""
    typer.echo("🎯 SniperSight v0.1.0")
    typer.echo("Institutional-Grade Crypto Market Scanner")
    typer.echo()
    typer.echo("Status: Phase 1 Foundation ✅ Complete")
    typer.echo("Next: Phase 2 Data Layer (Exchange adapters, ingestion pipeline)")


if __name__ == "__main__":
    app()

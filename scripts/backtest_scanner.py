"""
Lightweight backtest runner for the SniperSight scanner.

Uses a mock adapter to generate deterministic OHLCV and runs the
Orchestrator pipeline over a small universe to summarize signal stats.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import argparse
import pandas as pd
import numpy as np

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.engine.orchestrator import Orchestrator
from backend.data.adapters.mocks import generate_trending_data, generate_ranging_data, generate_volatile_data


SUPPORTED_TFS = ("1H", "4H", "1D")


class MockAdapter:
	"""Simple adapter that returns synthetic OHLCV for requested timeframe."""

	def __init__(self, regime_map: Dict[str, str] | None = None):
		# Map symbol -> regime name
		self.regime_map = regime_map or {}

	def _gen(self, symbol: str) -> pd.DataFrame:
		regime = self.regime_map.get(symbol, "ranging")
		if regime == "trending":
			data = generate_trending_data(bars=100)
		elif regime == "volatile":
			data = generate_volatile_data(bars=100)
		else:
			data = generate_ranging_data(bars=100)

		df = pd.DataFrame([{
			'timestamp': x.timestamp,
			'open': x.open,
			'high': x.high,
			'low': x.low,
			'close': x.close,
			'volume': x.volume,
		} for x in data])
		df = df.sort_values('timestamp').reset_index(drop=True)
		df = df.set_index('timestamp', drop=False)
		return df

	def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
		df = self._gen(symbol)
		# Resample to requested timeframe if supported
		if timeframe not in SUPPORTED_TFS:
			# Map 15m/5m to 1H for simplicity in mock
			timeframe = "1H"
		rule = {"1H": '1H', "4H": '4H', "1D": '1D'}[timeframe]
		o = df.resample(rule, label='right', closed='right').agg({
			'open': 'first',
			'high': 'max',
			'low': 'min',
			'close': 'last',
			'volume': 'sum'
		}).dropna().reset_index()
		o = o.tail(min(limit, len(o)))
		# Ensure timestamp column exists
		o = o.rename(columns={'timestamp': 'timestamp'})
		return o


def _extract_factor_scores(plans):
	rows = []
	for p in plans:
		bd = getattr(p, 'confluence_breakdown', None)
		if not bd:
			continue
		factor_map = {f.name: f.score for f in bd.factors}
		rows.append({
			'symbol': p.symbol,
			'direction': p.direction,
			'total_score': bd.total_score,
			**factor_map
		})
	return pd.DataFrame(rows) if rows else pd.DataFrame()


def run_backtest(multi: bool = False):
	# Universe and regimes
	base_symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'LINK/USDT']
	scenarios = [
		('mixed', {
			'BTC/USDT': 'trending', 'ETH/USDT': 'ranging', 'SOL/USDT': 'volatile', 'LINK/USDT': 'ranging'
		}),
		('all_trending', {s: 'trending' for s in base_symbols}),
		('all_ranging', {s: 'ranging' for s in base_symbols}),
		('all_volatile', {s: 'volatile' for s in base_symbols}),
	]

	aggregate_frames = []

	def _run_single(label: str, regime_map: Dict[str, str]):
		adapter = MockAdapter(regime_map=regime_map)
		cfg = ScanConfig(profile='recon')
		mode = get_mode('recon')
		tf_union = tuple([tf for tf in mode.timeframes if tf in SUPPORTED_TFS])
		cfg.timeframes = tf_union if tf_union else SUPPORTED_TFS
		cfg.min_confluence_score = mode.min_confluence_score
		cfg.primary_planning_timeframe = mode.primary_planning_timeframe
		cfg.entry_timeframes = mode.entry_timeframes
		cfg.structure_timeframes = mode.structure_timeframes
		cfg.stop_timeframes = getattr(mode, 'stop_timeframes', ())
		cfg.target_timeframes = getattr(mode, 'target_timeframes', ())
		try:
			mode.critical_timeframes = tuple([tf for tf in getattr(mode, 'critical_timeframes', SUPPORTED_TFS) if tf in SUPPORTED_TFS])
		except Exception:
			pass
		orch = Orchestrator(config=cfg, exchange_adapter=adapter, debug_mode=False, concurrency_workers=4)
		orch.apply_mode(mode)
		plans, rej = orch.scan(base_symbols)
		df = _extract_factor_scores(plans)
		df['scenario'] = label
		return plans, rej, df

	if multi:
		print("=== Multi-Scenario Backtest ===")
		scenario_results = []
		for label, regime_map in scenarios:
			plans, rej, df = _run_single(label, regime_map)
			aggregate_frames.append(df)
			scenario_results.append((label, plans, rej))
			print(f"Scenario: {label}")
			print(f"  Signals: {len(plans)} | Rejected: {rej['total_rejected']} (low_confluence={rej['by_reason']['low_confluence']})")
		if aggregate_frames:
			all_df = pd.concat(aggregate_frames, ignore_index=True)
			if not all_df.empty:
				print("\nFactor Averages by Scenario (incl. Volatility & Volume):")
				agg_map = {
					'total_score': 'mean',
					'Momentum': 'mean',
					'Volatility': 'mean',
					'Volume': 'mean',
					'Market Structure': 'mean'
				}
				pivot = all_df.groupby('scenario').agg({k: v for k, v in agg_map.items() if k in all_df.columns}).round(2)
				print(pivot.to_string())
				# Momentum contribution distribution
				print("\nMomentum Score Distribution (all scenarios):")
				desc = all_df['Momentum'].describe().round(2)
				print(desc.to_string())
				# Volatility contribution distribution
				if 'Volatility' in all_df.columns:
					print("\nVolatility Score Distribution (all scenarios):")
					vdesc = all_df['Volatility'].describe().round(2)
					print(vdesc.to_string())
				# Per-signal breakdown sample
				print("\nSample Signal Breakdown:")
				cols = ['scenario', 'symbol', 'direction', 'total_score']
				for c in ['Momentum', 'Volatility', 'Volume', 'HTF Alignment', 'Order Block', 'Fair Value Gap']:
					if c in all_df.columns:
						cols.append(c)
				sample = all_df[cols].head(10).round(2)
				print(sample.to_string(index=False))
		return

	# Single scenario default (mixed)
	regime_map = scenarios[0][1]
	symbols = base_symbols

	adapter = MockAdapter(regime_map=regime_map)
	cfg = ScanConfig(profile='recon')
	mode = get_mode('recon')
	tf_union = tuple([tf for tf in mode.timeframes if tf in SUPPORTED_TFS])
	cfg.timeframes = tf_union if tf_union else SUPPORTED_TFS
	cfg.min_confluence_score = mode.min_confluence_score
	cfg.primary_planning_timeframe = mode.primary_planning_timeframe
	cfg.entry_timeframes = mode.entry_timeframes
	cfg.structure_timeframes = mode.structure_timeframes
	cfg.stop_timeframes = getattr(mode, 'stop_timeframes', ())
	cfg.target_timeframes = getattr(mode, 'target_timeframes', ())
	try:
		mode.critical_timeframes = tuple([tf for tf in getattr(mode, 'critical_timeframes', SUPPORTED_TFS) if tf in SUPPORTED_TFS])
	except Exception:
		pass
	orch = Orchestrator(config=cfg, exchange_adapter=adapter, debug_mode=False, concurrency_workers=4)
	orch.apply_mode(mode)

	signals, rejections = orch.scan(symbols)

	print("=== Backtest Summary ===")
	print(f"Symbols scanned: {len(symbols)}")
	print(f"Signals generated: {len(signals)}")
	print(f"Rejections: {rejections['total_rejected']}")
	print("By reason:")
	for k, v in rejections['by_reason'].items():
		print(f"  - {k}: {v}")

	if signals:
		print("\nTop signals:")
		for s in sorted(signals, key=lambda x: x.confidence_score, reverse=True)[:3]:
			tf_meta = s.metadata.get('tf_responsibility', {})
			print(f"  {s.symbol} | {s.direction} | score={s.confidence_score:.1f} | RR={s.risk_reward:.2f} | entryTF={tf_meta.get('entry_timeframe')} targetTF={tf_meta.get('tp_timeframe')}")
		# Factor breakdown summary
		df = _extract_factor_scores(signals)
		if not df.empty:
			print("\nMomentum factor stats:")
			print(df['Momentum'].describe().round(2).to_string())
			print("\nStructure vs Momentum correlation (Pearson):")
			if 'Market Structure' in df.columns:
				corr = df['Momentum'].corr(df['Market Structure'])
				print(f"  corr={corr:.3f}")


def main():
	parser = argparse.ArgumentParser(description="Backtest SniperSight scanner (mock data)")
	parser.add_argument('--multi', action='store_true', help='Run multi-scenario backtest')
	args = parser.parse_args()
	run_backtest(multi=args.multi)


if __name__ == "__main__":
	main()


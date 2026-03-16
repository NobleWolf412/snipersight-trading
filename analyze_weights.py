
weights = {
    "order_block": 0.18,
    "fvg": 0.12,
    "market_structure": 0.28,
    "liquidity_sweep": 0.12,
    "kill_zone": 0.08,
    "momentum": 0.15,
    "divergence": 0.18,
    "fibonacci": 0.10,
    "volume": 0.10,
    "volatility": 0.10,
    "htf_alignment": 0.12,
    "htf_momentum_gate": 0.07,
    "regime_alignment": 0.07,
    "htf_proximity": 0.10,
    "btc_impulse": 0.08,
    "weekly_stoch_rsi": 0.06,
    "htf_structure_bias": 0.10,
    "premium_discount": 0.10,
    "inside_ob": 0.10,
    "nested_ob": 0.08,
    "opposing_structure": 0.10,
    "htf_inflection": 0.10,
    "multi_tf_reversal": 0.12,
    "ltf_structure_shift": 0.10,
    "institutional_sequence": 0.12,
    "timeframe_conflict": 0.12,
    "macd_veto": 0.05,
    "close_momentum": 0.08,
    "multi_close_confirm": 0.07,
    "liquidity_draw": 0.12,
}

total = sum(weights.values())
print(f"Total: {total}")
for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True):
    norm = v / total
    print(f"{k:25}: {v:.2f} -> {norm:.4f} ({norm*100:.1f}%)")

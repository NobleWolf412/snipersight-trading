
modes = {
    "macro_surveillance": {
        "order_block": 0.25, "fvg": 0.18, "market_structure": 0.20, "liquidity_sweep": 0.18,
        "kill_zone": 0.03, "momentum": 0.08, "divergence": 0.15, "fibonacci": 0.10,
        "volume": 0.10, "volatility": 0.08, "htf_alignment": 0.25, "htf_momentum_gate": 0.10,
        "regime_alignment": 0.10, "htf_proximity": 0.15, "btc_impulse": 0.12,
        "weekly_stoch_rsi": 0.12, "htf_structure_bias": 0.15, "premium_discount": 0.15,
        "inside_ob": 0.10, "nested_ob": 0.10, "opposing_structure": 0.06, "htf_inflection": 0.18,
        "multi_tf_reversal": 0.12, "ltf_structure_shift": 0.05, "institutional_sequence": 0.15,
        "timeframe_conflict": 0.10, "macd_veto": 0.05, "close_momentum": 0.06,
        "multi_close_confirm": 0.08, "liquidity_draw": 0.08,
    },
    "intraday_aggressive": {
        "order_block": 0.18, "fvg": 0.12, "market_structure": 0.28, "liquidity_sweep": 0.12,
        "kill_zone": 0.08, "momentum": 0.15, "divergence": 0.18, "fibonacci": 0.10,
        "volume": 0.10, "volatility": 0.10, "htf_alignment": 0.12, "htf_momentum_gate": 0.07,
        "regime_alignment": 0.07, "htf_proximity": 0.10, "btc_impulse": 0.08,
        "weekly_stoch_rsi": 0.06, "htf_structure_bias": 0.10, "premium_discount": 0.10,
        "inside_ob": 0.10, "nested_ob": 0.08, "opposing_structure": 0.10, "htf_inflection": 0.10,
        "multi_tf_reversal": 0.12, "ltf_structure_shift": 0.10, "institutional_sequence": 0.12,
        "timeframe_conflict": 0.12, "macd_veto": 0.05, "close_momentum": 0.08,
        "multi_close_confirm": 0.07, "liquidity_draw": 0.12,
    },
    "precision": {
        "order_block": 0.15, "fvg": 0.10, "market_structure": 0.30, "liquidity_sweep": 0.10,
        "kill_zone": 0.10, "momentum": 0.12, "divergence": 0.16, "fibonacci": 0.10,
        "volume": 0.08, "volatility": 0.12, "htf_alignment": 0.10, "htf_momentum_gate": 0.05,
        "regime_alignment": 0.05, "htf_proximity": 0.08, "btc_impulse": 0.05,
        "weekly_stoch_rsi": 0.05, "htf_structure_bias": 0.08, "premium_discount": 0.12,
        "inside_ob": 0.10, "nested_ob": 0.05, "opposing_structure": 0.12, "htf_inflection": 0.08,
        "multi_tf_reversal": 0.10, "ltf_structure_shift": 0.12, "institutional_sequence": 0.10,
        "timeframe_conflict": 0.15, "macd_veto": 0.05, "close_momentum": 0.09,
        "multi_close_confirm": 0.06, "liquidity_draw": 0.15,
    },
    "stealth_balanced": {
        "order_block": 0.20, "fvg": 0.15, "market_structure": 0.25, "liquidity_sweep": 0.15,
        "kill_zone": 0.10, "momentum": 0.10, "divergence": 0.15, "fibonacci": 0.10,
        "volume": 0.10, "volatility": 0.08, "htf_alignment": 0.18, "htf_momentum_gate": 0.08,
        "regime_alignment": 0.08, "htf_proximity": 0.12, "btc_impulse": 0.10,
        "weekly_stoch_rsi": 0.10, "htf_structure_bias": 0.12, "premium_discount": 0.12,
        "inside_ob": 0.10, "nested_ob": 0.08, "opposing_structure": 0.08, "htf_inflection": 0.12,
        "multi_tf_reversal": 0.12, "ltf_structure_shift": 0.08, "institutional_sequence": 0.12,
        "timeframe_conflict": 0.10, "macd_veto": 0.05, "close_momentum": 0.07,
        "multi_close_confirm": 0.08, "liquidity_draw": 0.10,
    }
}

for name, weights in modes.items():
    total = sum(weights.values())
    print(f'    "{name}": {{')
    for k, v in weights.items():
        norm = v / total
        print(f'        "{k}": {norm:.3f},')
    print("    },")

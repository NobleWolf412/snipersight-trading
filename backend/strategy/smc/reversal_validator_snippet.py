
def validate_reversal_profile(reversal: ReversalContext, profile: str = 'balanced') -> ReversalContext:
    """
    Validate reversal quality against scanner mode requirements.
    
    Modes apply different gates:
    - Surgical/Precision: Requires High Confidence (>75%) OR robust signal count (3+).
    - Overwatch/Macro: Requires Cycle Alignment (DCL/WCL/LTR).
    - Stealth: Requires 'Hidden' intent (Liquidity Sweep or Volume Displacement).
    - Strike/Aggressive: Standard Confidence (>50%).
    
    If validation fails, returns a context with is_reversal_setup=False
    and an updated rationale explaining the rejection.
    """
    if not reversal.is_reversal_setup:
        return reversal
        
    profile = profile.lower()
    reject_reason = ""
    
    # 1. Surgical/Precision (Strict Quality)
    if profile in ('surgical', 'precision'):
        # Require High Confidence OR 3+ Components
        # htf_bypass_active usually implies high structural quality
        is_high_quality = reversal.confidence >= 75.0 or reversal.htf_bypass_active
        if not is_high_quality:
            # Check component count manually if htf_bypass not active
            comp_count = sum([reversal.cycle_aligned, reversal.choch_detected, 
                              reversal.volume_displacement, reversal.liquidity_swept])
            if comp_count < 3:
                reject_reason = f"Surgical requires High Conf (75%+) or 3+ Signals. Current: {reversal.confidence:.0f}% / {comp_count}"

    # 2. Overwatch/Macro (Strict Structure/Cycle)
    elif profile in ('overwatch', 'macro_surveillance'):
        # Must be cycle aligned (TopDown approach)
        if not reversal.cycle_aligned:
             reject_reason = "Overwatch requires Cycle Alignment (DCL/WCL/LTR)"

    # 3. Stealth (Smart Money Footprint)
    elif 'stealth' in profile:
        # Must have "Hidden" signs: Sweep or Volume (CHoCH alone is too obvious/late)
        if not (reversal.liquidity_swept or reversal.volume_displacement):
            reject_reason = "Stealth requires Liquidity Sweep or Volume Displacement"

    # 4. Strike/Aggressive (Momentum)
    elif profile in ('strike', 'intraday_aggressive'):
        if reversal.confidence < 50.0:
            reject_reason = f"Strike requires min 50% confidence. Current: {reversal.confidence:.0f}%"

    if reject_reason:
        # Return modified copy
        from dataclasses import replace
        return replace(reversal, is_reversal_setup=False, rationale=f"⛔ {reject_reason}")
    
    return reversal

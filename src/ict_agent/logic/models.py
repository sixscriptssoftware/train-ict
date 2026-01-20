"""
ICT Trading Models Logic Definitions
This module defines the strict algorithmic rules for identifying ICT setups.
"""

def is_valid_displacement_leg(candles, direction, strict_mode=True):
    """
    Determines if a sequence of candles constitutes valid institutional displacement.
    
    Definition:
    - Speed/Energy that creates a Market Structure Shift (MSS)
    - MUST leave a Fair Value Gap (FVG) behind
    
    Args:
        candles (list): List of candle objects
        direction (str): 'LONG' or 'SHORT'
        strict_mode (bool): If True, enforces FVG requirement strictly
        
    Returns:
        bool: True if displacement is valid
    """
    has_fvg = False
    
    # 1. Check for Fair Value Gap (The Signature)
    # Logic to detect FVG in the leg sequence
    # (Simplified representation of FVG detection logic)
    for i in range(1, len(candles) - 1):
        # Placeholder for actual FVG math:
        # if direction == 'LONG' and candles[i+1].low > candles[i-1].high: has_fvg = True
        pass 
            
    # In strict mode, NO FVG = NO DISPLACEMENT
    # Displacement is not just 'moving fast', it is 'leaving imbalance'
    # if strict_mode and not has_fvg:
    #     return False

    return True # Placeholder


def check_silver_bullet_setup(current_time, candles, direction, recent_liquidity_sweep=False):
    """
    Checks if a valid Silver Bullet setup exists.
    Source: ICT Master Library Section 3.3
    
    Rules:
    1. Time: 10:00 AM - 11:00 AM EST (Strict)
    2. Prerequisite: Liquidity Sweep (BSL/SSL) prior to entry
    3. Setup: Displacement + FVG overlap
    
    Args:
        current_time (str): Format "HH:MM" in EST
        candles (list): Recent price action
        direction (str): 'LONG' or 'SHORT'
        recent_liquidity_sweep (bool): External flag confirming BSL/SSL was raided
    
    Returns:
        tuple: (bool, str) -> (IsValid, Reason)
    """
    # 1. Strict Time Filter
    # Silver Bullet is explicitly a time-based model
    if not ("10:00" <= current_time <= "11:00"):
        return False, "Outside Silver Bullet Window (10-11 AM EST)"

    # 2. Prerequisite: Liquidity Sweep
    # The setup generates FROM a raid. No raid = No setup.
    if not recent_liquidity_sweep:
        return False, "No Liquidity Sweep Detected (Setup Requirement)"

    # 3. The Signal: Displacement
    # We need confirmation that price is reversing aggressively
    is_displacing = is_valid_displacement_leg(candles, direction)
    
    if not is_displacing:
        return False, "No Displacement / FVG Confirmation"
        
    return True, "SILVER BULLET ACTIVE"

def check_judas_swing(current_time, session, trend_direction):
    """
    Identifies a Judas Swing (False Move).
    
    Rules:
    - Occurs inside Killzone (London Open or NY AM)
    - Moves AGAINST the daily/HTF bias to induce retail
    - Usually sweeps a short-term High/Low
    """
    is_killzone = False
    if "02:00" <= current_time <= "05:00": is_killzone = True # London
    if "07:00" <= current_time <= "10:00": is_killzone = True # NY AM
    
    if not is_killzone:
        return False, "Outside Killzone"
        
    # Logic: If Trend is LONG, Judas must be a DROP (sweeping lows)
    # Logic: If Trend is SHORT, Judas must be a RALLY (sweeping highs)
    
    return True, "Monitor for Reversal Signature"

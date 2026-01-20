#!/usr/bin/env python3
"""
🎯 VEX ICT DYNAMIC LEVELS 🎯

Proper ICT trade management with dynamic SL/TP based on:
- Stop Loss: Above/below swing that created the setup
- Take Profit: Next liquidity pool
- Entry: 50% retracement of FVG

This is how ICT ACTUALLY trades.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")

import pandas as pd
import numpy as np


@dataclass
class ICTSetupLevels:
    """Dynamic ICT trade levels"""
    direction: str  # LONG or SHORT
    
    # Entry
    entry_price: float
    entry_type: str  # "FVG_50", "OB_RETEST", "DISPLACEMENT"
    
    # Stop Loss (dynamic based on structure)
    stop_loss: float
    sl_reason: str  # "Above swing high", "Above FVG", etc.
    sl_pips: float
    
    # Take Profit (based on liquidity)
    take_profit_1: float  # First target
    tp1_reason: str
    tp1_pips: float
    
    take_profit_2: Optional[float] = None  # Second target
    tp2_reason: Optional[str] = None
    tp2_pips: Optional[float] = None
    
    take_profit_3: Optional[float] = None  # Final target
    tp3_reason: Optional[str] = None
    tp3_pips: Optional[float] = None
    
    # Risk:Reward
    risk_reward_1: float = 0
    risk_reward_2: Optional[float] = None
    risk_reward_3: Optional[float] = None
    
    # Confidence
    setup_score: int = 0
    confluences: List[str] = None
    
    def __post_init__(self):
        if self.confluences is None:
            self.confluences = []


class ICTLevelCalculator:
    """
    Calculate proper ICT entry, SL, and TP levels.
    
    ICT Rules:
    - SL goes ABOVE the high that created the bearish FVG (shorts)
    - SL goes BELOW the low that created the bullish FVG (longs)
    - TP targets the next liquidity pool
    - Entry at 50% of FVG or Order Block
    """
    
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size
    
    def find_swing_high(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[float, int]:
        """Find the most recent swing high"""
        highs = df['high'].iloc[-lookback:]
        
        for i in range(len(highs) - 3, 1, -1):
            if (highs.iloc[i] > highs.iloc[i-1] and 
                highs.iloc[i] > highs.iloc[i-2] and
                highs.iloc[i] > highs.iloc[i+1] and
                highs.iloc[i] > highs.iloc[i+2]):
                return highs.iloc[i], len(df) - lookback + i
        
        return highs.max(), len(df) - lookback + highs.argmax()
    
    def find_swing_low(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[float, int]:
        """Find the most recent swing low"""
        lows = df['low'].iloc[-lookback:]
        
        for i in range(len(lows) - 3, 1, -1):
            if (lows.iloc[i] < lows.iloc[i-1] and
                lows.iloc[i] < lows.iloc[i-2] and
                lows.iloc[i] < lows.iloc[i+1] and
                lows.iloc[i] < lows.iloc[i+2]):
                return lows.iloc[i], len(df) - lookback + i
        
        return lows.min(), len(df) - lookback + lows.argmin()
    
    def find_fvg(self, df: pd.DataFrame, direction: str) -> Optional[dict]:
        """Find the most recent FVG in the given direction"""
        for i in range(len(df) - 1, 2, -1):
            if direction == "SHORT":
                # Bearish FVG: candle[i-2] low > candle[i] high
                if df['low'].iloc[i-2] > df['high'].iloc[i]:
                    return {
                        'type': 'bearish',
                        'high': df['low'].iloc[i-2],  # Top of gap
                        'low': df['high'].iloc[i],     # Bottom of gap
                        'midpoint': (df['low'].iloc[i-2] + df['high'].iloc[i]) / 2,
                        'idx': i,
                        'time': df.index[i]
                    }
            else:  # LONG
                # Bullish FVG: candle[i-2] high < candle[i] low
                if df['high'].iloc[i-2] < df['low'].iloc[i]:
                    return {
                        'type': 'bullish',
                        'high': df['low'].iloc[i],     # Top of gap
                        'low': df['high'].iloc[i-2],   # Bottom of gap
                        'midpoint': (df['low'].iloc[i] + df['high'].iloc[i-2]) / 2,
                        'idx': i,
                        'time': df.index[i]
                    }
        return None
    
    def find_liquidity_targets(self, df: pd.DataFrame, direction: str, 
                               current_price: float) -> List[dict]:
        """Find liquidity pools to target"""
        targets = []
        
        if direction == "SHORT":
            # Look for sellside liquidity (swing lows below current price)
            for i in range(len(df) - 3, 2, -1):
                if (df['low'].iloc[i] < df['low'].iloc[i-1] and
                    df['low'].iloc[i] < df['low'].iloc[i+1] and
                    df['low'].iloc[i] < current_price):
                    targets.append({
                        'type': 'sellside_liquidity',
                        'price': df['low'].iloc[i],
                        'idx': i,
                        'distance_pips': (current_price - df['low'].iloc[i]) / self.pip_size
                    })
        else:  # LONG
            # Look for buyside liquidity (swing highs above current price)
            for i in range(len(df) - 3, 2, -1):
                if (df['high'].iloc[i] > df['high'].iloc[i-1] and
                    df['high'].iloc[i] > df['high'].iloc[i+1] and
                    df['high'].iloc[i] > current_price):
                    targets.append({
                        'type': 'buyside_liquidity',
                        'price': df['high'].iloc[i],
                        'idx': i,
                        'distance_pips': (df['high'].iloc[i] - current_price) / self.pip_size
                    })
        
        # Sort by distance (closest first)
        targets.sort(key=lambda x: x['distance_pips'])
        return targets[:3]  # Return up to 3 targets
    
    def calculate_short_levels(self, df: pd.DataFrame) -> Optional[ICTSetupLevels]:
        """Calculate dynamic levels for a SHORT trade"""
        
        current_price = df['close'].iloc[-1]
        
        # Find FVG for entry
        fvg = self.find_fvg(df, "SHORT")
        if not fvg:
            return None
        
        # Entry at 50% of FVG
        entry_price = fvg['midpoint']
        
        # Stop Loss: Above the swing high that created the FVG
        # Or above the FVG itself + buffer
        swing_high, swing_idx = self.find_swing_high(df.iloc[:fvg['idx']+1], lookback=15)
        
        # SL is above the swing high + buffer (5 pips)
        buffer = 5 * self.pip_size
        stop_loss = swing_high + buffer
        sl_pips = (stop_loss - entry_price) / self.pip_size
        
        # If SL is too far (>50 pips), use FVG top + buffer instead
        if sl_pips > 50:
            stop_loss = fvg['high'] + buffer
            sl_pips = (stop_loss - entry_price) / self.pip_size
            sl_reason = f"Above FVG top + 5 pip buffer"
        else:
            sl_reason = f"Above swing high @ {swing_high:.5f} + buffer"
        
        # Take Profit: Next liquidity pools
        targets = self.find_liquidity_targets(df, "SHORT", entry_price)
        
        if not targets:
            # Fallback: use 2:1 minimum R:R
            tp1 = entry_price - (sl_pips * 2 * self.pip_size)
            tp1_reason = "2:1 R:R (no liquidity found)"
            tp1_pips = sl_pips * 2
        else:
            tp1 = targets[0]['price']
            tp1_reason = f"Sellside liquidity @ {tp1:.5f}"
            tp1_pips = (entry_price - tp1) / self.pip_size
        
        # Additional targets if available
        tp2 = targets[1]['price'] if len(targets) > 1 else None
        tp2_reason = f"Sellside liquidity @ {tp2:.5f}" if tp2 else None
        tp2_pips = (entry_price - tp2) / self.pip_size if tp2 else None
        
        tp3 = targets[2]['price'] if len(targets) > 2 else None
        tp3_reason = f"Sellside liquidity @ {tp3:.5f}" if tp3 else None
        tp3_pips = (entry_price - tp3) / self.pip_size if tp3 else None
        
        # Risk:Reward calculations
        rr1 = tp1_pips / sl_pips if sl_pips > 0 else 0
        rr2 = tp2_pips / sl_pips if tp2_pips and sl_pips > 0 else None
        rr3 = tp3_pips / sl_pips if tp3_pips and sl_pips > 0 else None
        
        # Confluences
        confluences = [
            f"Bearish FVG @ {fvg['high']:.5f}-{fvg['low']:.5f}",
            f"Entry at 50% FVG: {entry_price:.5f}",
            sl_reason,
        ]
        for t in targets:
            confluences.append(f"Target: {t['type']} @ {t['price']:.5f} ({t['distance_pips']:.0f} pips)")
        
        return ICTSetupLevels(
            direction="SHORT",
            entry_price=entry_price,
            entry_type="FVG_50",
            stop_loss=stop_loss,
            sl_reason=sl_reason,
            sl_pips=sl_pips,
            take_profit_1=tp1,
            tp1_reason=tp1_reason,
            tp1_pips=tp1_pips,
            take_profit_2=tp2,
            tp2_reason=tp2_reason,
            tp2_pips=tp2_pips,
            take_profit_3=tp3,
            tp3_reason=tp3_reason,
            tp3_pips=tp3_pips,
            risk_reward_1=rr1,
            risk_reward_2=rr2,
            risk_reward_3=rr3,
            setup_score=len(confluences) * 10,
            confluences=confluences
        )
    
    def calculate_long_levels(self, df: pd.DataFrame) -> Optional[ICTSetupLevels]:
        """Calculate dynamic levels for a LONG trade"""
        
        current_price = df['close'].iloc[-1]
        
        # Find FVG for entry
        fvg = self.find_fvg(df, "LONG")
        if not fvg:
            return None
        
        # Entry at 50% of FVG
        entry_price = fvg['midpoint']
        
        # Stop Loss: Below the swing low that created the FVG
        swing_low, swing_idx = self.find_swing_low(df.iloc[:fvg['idx']+1], lookback=15)
        
        # SL is below the swing low - buffer (5 pips)
        buffer = 5 * self.pip_size
        stop_loss = swing_low - buffer
        sl_pips = (entry_price - stop_loss) / self.pip_size
        
        # If SL is too far (>50 pips), use FVG bottom - buffer instead
        if sl_pips > 50:
            stop_loss = fvg['low'] - buffer
            sl_pips = (entry_price - stop_loss) / self.pip_size
            sl_reason = f"Below FVG bottom - 5 pip buffer"
        else:
            sl_reason = f"Below swing low @ {swing_low:.5f} - buffer"
        
        # Take Profit: Next liquidity pools
        targets = self.find_liquidity_targets(df, "LONG", entry_price)
        
        if not targets:
            # Fallback: use 2:1 minimum R:R
            tp1 = entry_price + (sl_pips * 2 * self.pip_size)
            tp1_reason = "2:1 R:R (no liquidity found)"
            tp1_pips = sl_pips * 2
        else:
            tp1 = targets[0]['price']
            tp1_reason = f"Buyside liquidity @ {tp1:.5f}"
            tp1_pips = (tp1 - entry_price) / self.pip_size
        
        # Additional targets
        tp2 = targets[1]['price'] if len(targets) > 1 else None
        tp2_reason = f"Buyside liquidity @ {tp2:.5f}" if tp2 else None
        tp2_pips = (tp2 - entry_price) / self.pip_size if tp2 else None
        
        tp3 = targets[2]['price'] if len(targets) > 2 else None
        tp3_reason = f"Buyside liquidity @ {tp3:.5f}" if tp3 else None
        tp3_pips = (tp3 - entry_price) / self.pip_size if tp3 else None
        
        # Risk:Reward
        rr1 = tp1_pips / sl_pips if sl_pips > 0 else 0
        rr2 = tp2_pips / sl_pips if tp2_pips and sl_pips > 0 else None
        rr3 = tp3_pips / sl_pips if tp3_pips and sl_pips > 0 else None
        
        # Confluences
        confluences = [
            f"Bullish FVG @ {fvg['low']:.5f}-{fvg['high']:.5f}",
            f"Entry at 50% FVG: {entry_price:.5f}",
            sl_reason,
        ]
        for t in targets:
            confluences.append(f"Target: {t['type']} @ {t['price']:.5f} ({t['distance_pips']:.0f} pips)")
        
        return ICTSetupLevels(
            direction="LONG",
            entry_price=entry_price,
            entry_type="FVG_50",
            stop_loss=stop_loss,
            sl_reason=sl_reason,
            sl_pips=sl_pips,
            take_profit_1=tp1,
            tp1_reason=tp1_reason,
            tp1_pips=tp1_pips,
            take_profit_2=tp2,
            tp2_reason=tp2_reason,
            tp2_pips=tp2_pips,
            take_profit_3=tp3,
            tp3_reason=tp3_reason,
            tp3_pips=tp3_pips,
            risk_reward_1=rr1,
            risk_reward_2=rr2,
            risk_reward_3=rr3,
            setup_score=len(confluences) * 10,
            confluences=confluences
        )


def test_dynamic_levels():
    """Test the dynamic level calculator"""
    from ict_agent.data.oanda_fetcher import OANDAFetcher
    
    print("╔" + "═"*58 + "╗")
    print("║" + "  🎯 ICT DYNAMIC LEVELS TEST 🎯".center(58) + "║")
    print("╚" + "═"*58 + "╝")
    
    fetcher = OANDAFetcher()
    df = fetcher.fetch_latest("EUR_USD", "15m", 100)
    
    if df.empty:
        print("No data!")
        return
    
    calculator = ICTLevelCalculator(pip_size=0.0001)
    
    # Test SHORT levels
    print("\n📉 SHORT SETUP LEVELS:")
    print("=" * 50)
    
    short_levels = calculator.calculate_short_levels(df)
    if short_levels:
        print(f"\n  Direction:     {short_levels.direction}")
        print(f"  Entry Type:    {short_levels.entry_type}")
        print(f"  Entry Price:   {short_levels.entry_price:.5f}")
        print(f"\n  Stop Loss:     {short_levels.stop_loss:.5f} ({short_levels.sl_pips:.1f} pips)")
        print(f"  SL Reason:     {short_levels.sl_reason}")
        print(f"\n  TP1:           {short_levels.take_profit_1:.5f} ({short_levels.tp1_pips:.1f} pips) - R:R {short_levels.risk_reward_1:.1f}")
        print(f"  TP1 Reason:    {short_levels.tp1_reason}")
        if short_levels.take_profit_2:
            print(f"\n  TP2:           {short_levels.take_profit_2:.5f} ({short_levels.tp2_pips:.1f} pips) - R:R {short_levels.risk_reward_2:.1f}")
            print(f"  TP2 Reason:    {short_levels.tp2_reason}")
        if short_levels.take_profit_3:
            print(f"\n  TP3:           {short_levels.take_profit_3:.5f} ({short_levels.tp3_pips:.1f} pips) - R:R {short_levels.risk_reward_3:.1f}")
            print(f"  TP3 Reason:    {short_levels.tp3_reason}")
        print(f"\n  Confluences:")
        for c in short_levels.confluences:
            print(f"    • {c}")
    else:
        print("  No bearish FVG found for SHORT setup")
    
    # Test LONG levels
    print("\n\n📈 LONG SETUP LEVELS:")
    print("=" * 50)
    
    long_levels = calculator.calculate_long_levels(df)
    if long_levels:
        print(f"\n  Direction:     {long_levels.direction}")
        print(f"  Entry Type:    {long_levels.entry_type}")
        print(f"  Entry Price:   {long_levels.entry_price:.5f}")
        print(f"\n  Stop Loss:     {long_levels.stop_loss:.5f} ({long_levels.sl_pips:.1f} pips)")
        print(f"  SL Reason:     {long_levels.sl_reason}")
        print(f"\n  TP1:           {long_levels.take_profit_1:.5f} ({long_levels.tp1_pips:.1f} pips) - R:R {long_levels.risk_reward_1:.1f}")
        print(f"  TP1 Reason:    {long_levels.tp1_reason}")
        if long_levels.take_profit_2:
            print(f"\n  TP2:           {long_levels.take_profit_2:.5f} ({long_levels.tp2_pips:.1f} pips) - R:R {long_levels.risk_reward_2:.1f}")
        if long_levels.take_profit_3:
            print(f"\n  TP3:           {long_levels.take_profit_3:.5f} ({long_levels.tp3_pips:.1f} pips) - R:R {long_levels.risk_reward_3:.1f}")
        print(f"\n  Confluences:")
        for c in long_levels.confluences:
            print(f"    • {c}")
    else:
        print("  No bullish FVG found for LONG setup")


if __name__ == "__main__":
    test_dynamic_levels()

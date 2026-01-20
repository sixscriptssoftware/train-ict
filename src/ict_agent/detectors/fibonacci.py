"""
Fibonacci and Premium/Discount Zone Detector

OTE = Optimal Trade Entry (62-79% retracement)
Premium = Above 50% (sell zone)
Discount = Below 50% (buy zone)
Equilibrium = 50%
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
import pandas as pd
import numpy as np


@dataclass
class FibLevel:
    """Fibonacci retracement level"""
    level: float  # 0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.79, 1.0
    price: float
    name: str  # "Equilibrium", "OTE Low", "OTE High", etc.


@dataclass
class FibZone:
    """A zone between two fib levels"""
    name: str
    top: float
    bottom: float
    levels: List[FibLevel]


@dataclass
class PremiumDiscount:
    """Premium/Discount analysis for a range"""
    range_high: float
    range_low: float
    equilibrium: float
    premium_zone: tuple  # (bottom, top)
    discount_zone: tuple  # (bottom, top)
    ote_zone: tuple  # (bottom, top) - 62-79%
    current_price: float
    price_position: Literal["PREMIUM", "DISCOUNT", "EQUILIBRIUM", "OTE"]


class FibonacciDetector:
    """
    Detects Fibonacci levels, OTE zones, and Premium/Discount.
    
    ICT Fibonacci Levels:
    - 0% = Swing low (for bullish) / Swing high (for bearish)
    - 50% = Equilibrium
    - 62% = OTE zone start
    - 70.5% = Optimal entry point
    - 79% = OTE zone end  
    - 100% = Swing high (for bullish) / Swing low (for bearish)
    
    Trading:
    - In bullish, buy in discount (below 50%) or OTE (62-79%)
    - In bearish, sell in premium (above 50%) or OTE (62-79% from high)
    """
    
    # ICT Fib levels
    FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.79, 1.0]
    FIB_NAMES = {
        0.0: "0% (Start)",
        0.236: "23.6%",
        0.382: "38.2%",
        0.5: "50% (Equilibrium)",
        0.618: "61.8% (OTE Low)",
        0.705: "70.5% (Optimal)",
        0.79: "79% (OTE High)",
        1.0: "100% (End)"
    }
    
    def __init__(self, swing_length: int = 10):
        self.swing_length = swing_length
    
    def detect(self, ohlc: pd.DataFrame, direction: Literal["BULLISH", "BEARISH"] = None) -> dict:
        """
        Detect fib levels and P/D zones.
        
        Returns:
            {
                'fib_levels': List[FibLevel],
                'premium_discount': PremiumDiscount,
                'ote_zone': FibZone,
                'in_ote': bool,
                'in_discount': bool,
                'in_premium': bool,
            }
        """
        # Find recent swing high and low
        swing_high, swing_low = self._find_swing_range(ohlc)
        
        if swing_high is None or swing_low is None:
            return {'error': 'Could not find swing range'}
        
        current_price = ohlc['close'].iloc[-1]
        
        # Determine direction if not provided
        if direction is None:
            # Use recent price action
            mid = (swing_high + swing_low) / 2
            if current_price > mid:
                direction = "BULLISH"
            else:
                direction = "BEARISH"
        
        # Calculate fib levels
        fib_levels = self._calculate_fib_levels(swing_high, swing_low, direction)
        
        # Calculate zones
        equilibrium = (swing_high + swing_low) / 2
        
        if direction == "BULLISH":
            # For bullish, discount is below equilibrium
            discount_zone = (swing_low, equilibrium)
            premium_zone = (equilibrium, swing_high)
            # OTE is 62-79% retracement from the high
            ote_low = swing_high - (swing_high - swing_low) * 0.618
            ote_high = swing_high - (swing_high - swing_low) * 0.79
            ote_zone = (ote_high, ote_low)  # Inverted because retracement
        else:
            # For bearish, premium is above equilibrium
            premium_zone = (equilibrium, swing_high)
            discount_zone = (swing_low, equilibrium)
            # OTE is 62-79% retracement from the low
            ote_low = swing_low + (swing_high - swing_low) * 0.618
            ote_high = swing_low + (swing_high - swing_low) * 0.79
            ote_zone = (ote_low, ote_high)
        
        # Determine current position
        if ote_zone[0] <= current_price <= ote_zone[1]:
            position = "OTE"
        elif current_price < equilibrium:
            position = "DISCOUNT"
        elif current_price > equilibrium:
            position = "PREMIUM"
        else:
            position = "EQUILIBRIUM"
        
        pd_analysis = PremiumDiscount(
            range_high=swing_high,
            range_low=swing_low,
            equilibrium=equilibrium,
            premium_zone=premium_zone,
            discount_zone=discount_zone,
            ote_zone=ote_zone,
            current_price=current_price,
            price_position=position
        )
        
        return {
            'fib_levels': fib_levels,
            'premium_discount': pd_analysis,
            'ote_zone': FibZone(
                name="OTE Zone (62-79%)",
                top=max(ote_zone),
                bottom=min(ote_zone),
                levels=[l for l in fib_levels if 0.618 <= l.level <= 0.79]
            ),
            'in_ote': position == "OTE",
            'in_discount': position == "DISCOUNT",
            'in_premium': position == "PREMIUM",
            'direction': direction,
        }
    
    def _find_swing_range(self, ohlc: pd.DataFrame) -> tuple:
        """Find the most recent significant swing high and low"""
        n = self.swing_length
        highs = ohlc['high'].values
        lows = ohlc['low'].values
        
        # Find swing highs
        swing_highs = []
        for i in range(n, len(ohlc) - n):
            if highs[i] == max(highs[i-n:i+n+1]):
                swing_highs.append((i, highs[i]))
        
        # Find swing lows
        swing_lows = []
        for i in range(n, len(ohlc) - n):
            if lows[i] == min(lows[i-n:i+n+1]):
                swing_lows.append((i, lows[i]))
        
        if not swing_highs or not swing_lows:
            # Fallback to recent high/low
            return ohlc['high'].max(), ohlc['low'].min()
        
        # Get most recent swing high and low
        recent_high = swing_highs[-1][1] if swing_highs else ohlc['high'].max()
        recent_low = swing_lows[-1][1] if swing_lows else ohlc['low'].min()
        
        return recent_high, recent_low
    
    def _calculate_fib_levels(
        self, 
        swing_high: float, 
        swing_low: float, 
        direction: str
    ) -> List[FibLevel]:
        """Calculate all fibonacci levels"""
        levels = []
        range_size = swing_high - swing_low
        
        for fib in self.FIB_LEVELS:
            if direction == "BULLISH":
                # For bullish, 0% is at low, 100% at high
                price = swing_low + (range_size * fib)
            else:
                # For bearish, 0% is at high, 100% at low
                price = swing_high - (range_size * fib)
            
            levels.append(FibLevel(
                level=fib,
                price=price,
                name=self.FIB_NAMES[fib]
            ))
        
        return levels
    
    def get_ote_entry(self, ohlc: pd.DataFrame, direction: str) -> Optional[dict]:
        """
        Get OTE entry level for a trade.
        
        Returns entry, stop, and targets based on fib levels.
        """
        result = self.detect(ohlc, direction)
        if 'error' in result:
            return None
        
        pd_zone = result['premium_discount']
        ote = result['ote_zone']
        
        if direction == "BULLISH":
            # Entry at 70.5% retracement, stop below 79%
            entry = pd_zone.equilibrium - (pd_zone.range_high - pd_zone.range_low) * 0.705
            stop = pd_zone.equilibrium - (pd_zone.range_high - pd_zone.range_low) * 0.79 - 0.0005
            target1 = pd_zone.range_high  # Previous high
            target2 = pd_zone.range_high + (pd_zone.range_high - pd_zone.range_low)  # Extension
        else:
            # Entry at 70.5% retracement up, stop above 79%
            entry = pd_zone.equilibrium + (pd_zone.range_high - pd_zone.range_low) * 0.705
            stop = pd_zone.equilibrium + (pd_zone.range_high - pd_zone.range_low) * 0.79 + 0.0005
            target1 = pd_zone.range_low
            target2 = pd_zone.range_low - (pd_zone.range_high - pd_zone.range_low)
        
        return {
            'entry': entry,
            'stop_loss': stop,
            'target_1': target1,
            'target_2': target2,
            'ote_zone': (ote.bottom, ote.top),
            'risk_pips': abs(entry - stop) / 0.0001,
            'reward_pips': abs(entry - target1) / 0.0001,
        }

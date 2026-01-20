"""
ICT Inducement Detector

Inducement = Obvious liquidity that's designed to trap traders
- Usually forms at recent swing highs/lows
- Gets swept before real move
- Part of "trap setup"
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
import pandas as pd
import numpy as np


@dataclass
class Inducement:
    """
    An inducement zone where retail is likely trapped.
    
    Think of it as "low hanging fruit liquidity" that's too obvious.
    """
    direction: Literal["BULLISH", "BEARISH"]  # Which side will get trapped
    level: float
    strength: Literal["WEAK", "MODERATE", "STRONG"]
    touches: int  # How many times price visited this level
    order_flow: str  # Where orders likely are ("ABOVE" or "BELOW" this level)
    trap_complete: bool  # Has it already been swept?
    
    def __repr__(self) -> str:
        status = "SWEPT" if self.trap_complete else "ACTIVE"
        return f"Inducement({self.direction} @ {self.level:.5f}, {self.strength}, {status})"


class InducementDetector:
    """
    Detects inducement (obvious liquidity traps).
    
    Inducement is:
    1. Recent swing high/low
    2. Multiple touches (makes it "obvious")
    3. Liquidity resting above/below
    4. Usually gets swept before real move
    """
    
    def __init__(self, pip_size: float = 0.0001, tolerance_pips: float = 5):
        self.pip_size = pip_size
        self.tolerance = tolerance_pips * pip_size
    
    def detect(self, ohlc: pd.DataFrame, swing_length: int = 5) -> List[Inducement]:
        """
        Detect inducement zones.
        
        Args:
            ohlc: OHLC data with columns [open, high, low, close]
            swing_length: Bars on each side for swing detection
        """
        if len(ohlc) < swing_length * 3:
            return []
        
        inducements = []
        
        # Find swing highs and lows
        swing_highs = self._find_swing_highs(ohlc, swing_length)
        swing_lows = self._find_swing_lows(ohlc, swing_length)
        
        current_price = ohlc['close'].iloc[-1]
        
        # Group similar swing highs (inducement = multiple touches)
        high_clusters = self._cluster_levels([h['level'] for h in swing_highs])
        low_clusters = self._cluster_levels([l['level'] for l in swing_lows])
        
        # Bullish inducement = swing highs that will trap shorts
        for cluster in high_clusters:
            level = cluster['level']
            touches = cluster['count']
            
            if touches >= 2:  # Multiple touches = more obvious
                # Check if swept
                swept = ohlc['high'].iloc[-swing_length:].max() > level
                
                # Strength based on touches
                if touches >= 4:
                    strength = "STRONG"
                elif touches >= 3:
                    strength = "MODERATE"
                else:
                    strength = "WEAK"
                
                # Only include if level is above current price (unless swept)
                if level > current_price or swept:
                    inducements.append(Inducement(
                        direction="BULLISH",  # Will trap shorts (BSL inducement)
                        level=level,
                        strength=strength,
                        touches=touches,
                        order_flow="ABOVE",
                        trap_complete=swept
                    ))
        
        # Bearish inducement = swing lows that will trap longs
        for cluster in low_clusters:
            level = cluster['level']
            touches = cluster['count']
            
            if touches >= 2:
                swept = ohlc['low'].iloc[-swing_length:].min() < level
                
                if touches >= 4:
                    strength = "STRONG"
                elif touches >= 3:
                    strength = "MODERATE"
                else:
                    strength = "WEAK"
                
                if level < current_price or swept:
                    inducements.append(Inducement(
                        direction="BEARISH",  # Will trap longs (SSL inducement)
                        level=level,
                        strength=strength,
                        touches=touches,
                        order_flow="BELOW",
                        trap_complete=swept
                    ))
        
        # Sort by strength
        strength_order = {"STRONG": 0, "MODERATE": 1, "WEAK": 2}
        inducements.sort(key=lambda x: (strength_order[x.strength], abs(x.level - current_price)))
        
        return inducements
    
    def _find_swing_highs(self, ohlc: pd.DataFrame, length: int) -> List[dict]:
        """Find swing highs."""
        highs = []
        for i in range(length, len(ohlc) - length):
            is_high = True
            pivot = ohlc['high'].iloc[i]
            for j in range(i - length, i + length + 1):
                if j != i and ohlc['high'].iloc[j] >= pivot:
                    is_high = False
                    break
            if is_high:
                highs.append({
                    'level': pivot,
                    'index': i,
                    'time': ohlc.index[i]
                })
        return highs
    
    def _find_swing_lows(self, ohlc: pd.DataFrame, length: int) -> List[dict]:
        """Find swing lows."""
        lows = []
        for i in range(length, len(ohlc) - length):
            is_low = True
            pivot = ohlc['low'].iloc[i]
            for j in range(i - length, i + length + 1):
                if j != i and ohlc['low'].iloc[j] <= pivot:
                    is_low = False
                    break
            if is_low:
                lows.append({
                    'level': pivot,
                    'index': i,
                    'time': ohlc.index[i]
                })
        return lows
    
    def _cluster_levels(self, levels: List[float]) -> List[dict]:
        """
        Group similar price levels together.
        Multiple touches at same level = inducement.
        """
        if not levels:
            return []
        
        clusters = []
        used = set()
        
        for i, level in enumerate(levels):
            if i in used:
                continue
            
            cluster_levels = [level]
            used.add(i)
            
            for j, other in enumerate(levels):
                if j not in used and abs(level - other) <= self.tolerance:
                    cluster_levels.append(other)
                    used.add(j)
            
            clusters.append({
                'level': sum(cluster_levels) / len(cluster_levels),
                'count': len(cluster_levels)
            })
        
        return clusters
    
    def get_active_inducement(self, ohlc: pd.DataFrame) -> Optional[Inducement]:
        """
        Get the most relevant active inducement.
        
        Returns closest unswept inducement to current price.
        """
        inducements = self.detect(ohlc)
        
        active = [i for i in inducements if not i.trap_complete]
        
        if not active:
            return None
        
        current_price = ohlc['close'].iloc[-1]
        return min(active, key=lambda x: abs(x.level - current_price))

"""
Equal Highs/Lows and Liquidity Pool Detector

Equal highs/lows are STRONG liquidity pools because:
- More stops clustered at similar levels
- More obvious to retail = more stops = bigger target for smart money
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
import pandas as pd
import numpy as np


@dataclass
class EqualLevel:
    """Equal high or low - strong liquidity pool"""
    prices: List[float]  # The prices that form the equal level
    avg_price: float
    type: Literal["EQUAL_HIGHS", "EQUAL_LOWS"]
    touches: int  # How many times price touched this level
    timestamps: List[pd.Timestamp]
    swept: bool = False
    sweep_timestamp: Optional[pd.Timestamp] = None


@dataclass 
class LiquidityPool:
    """Any significant liquidity level"""
    price: float
    type: Literal["BSL", "SSL"]  # Buyside or Sellside
    strength: Literal["WEAK", "MODERATE", "STRONG"]
    is_equal_level: bool
    touches: int
    swept: bool = False


class EqualLevelDetector:
    """
    Detects equal highs and equal lows - key liquidity targets.
    
    Equal Highs = Multiple swing highs at similar price
        - Buy-side liquidity (BSL)
        - Stops from shorts resting above
        - Target for bullish moves / reversal point for bears
        
    Equal Lows = Multiple swing lows at similar price
        - Sell-side liquidity (SSL)
        - Stops from longs resting below
        - Target for bearish moves / reversal point for bulls
    """
    
    def __init__(
        self,
        tolerance_pips: float = 5.0,  # How close prices need to be to count as "equal"
        min_touches: int = 2,  # Minimum touches to form equal level
        swing_length: int = 5,
        pip_size: float = 0.0001
    ):
        self.tolerance_pips = tolerance_pips
        self.min_touches = min_touches
        self.swing_length = swing_length
        self.pip_size = pip_size
    
    def detect(self, ohlc: pd.DataFrame) -> dict:
        """
        Detect equal highs/lows and all liquidity pools.
        
        Returns:
            {
                'equal_highs': List[EqualLevel],
                'equal_lows': List[EqualLevel],
                'bsl_pools': List[LiquidityPool],  # All buy-side liquidity
                'ssl_pools': List[LiquidityPool],  # All sell-side liquidity
                'unswept_equal_highs': List[EqualLevel],
                'unswept_equal_lows': List[EqualLevel],
            }
        """
        # First find all swing points
        swing_highs = self._find_swing_highs(ohlc)
        swing_lows = self._find_swing_lows(ohlc)
        
        # Find equal levels
        equal_highs = self._find_equal_levels(swing_highs, "EQUAL_HIGHS", ohlc)
        equal_lows = self._find_equal_levels(swing_lows, "EQUAL_LOWS", ohlc)
        
        # Check for sweeps
        current_price = ohlc['close'].iloc[-1]
        recent_high = ohlc['high'].iloc[-20:].max()
        recent_low = ohlc['low'].iloc[-20:].min()
        
        for eh in equal_highs:
            if recent_high > eh.avg_price:
                eh.swept = True
                # Find sweep timestamp
                for i in range(len(ohlc)-20, len(ohlc)):
                    if ohlc['high'].iloc[i] > eh.avg_price:
                        eh.sweep_timestamp = ohlc.index[i]
                        break
        
        for el in equal_lows:
            if recent_low < el.avg_price:
                el.swept = True
                for i in range(len(ohlc)-20, len(ohlc)):
                    if ohlc['low'].iloc[i] < el.avg_price:
                        el.sweep_timestamp = ohlc.index[i]
                        break
        
        # Build liquidity pools
        bsl_pools = self._build_liquidity_pools(swing_highs, equal_highs, "BSL", ohlc)
        ssl_pools = self._build_liquidity_pools(swing_lows, equal_lows, "SSL", ohlc)
        
        return {
            'equal_highs': equal_highs,
            'equal_lows': equal_lows,
            'bsl_pools': bsl_pools,
            'ssl_pools': ssl_pools,
            'unswept_equal_highs': [eh for eh in equal_highs if not eh.swept],
            'unswept_equal_lows': [el for el in equal_lows if not el.swept],
        }
    
    def _find_swing_highs(self, ohlc: pd.DataFrame) -> List[tuple]:
        """Find swing highs: (index, price, timestamp)"""
        swings = []
        highs = ohlc['high'].values
        n = self.swing_length
        
        for i in range(n, len(ohlc) - n):
            if highs[i] == max(highs[i-n:i+n+1]):
                swings.append((i, highs[i], ohlc.index[i]))
        
        return swings
    
    def _find_swing_lows(self, ohlc: pd.DataFrame) -> List[tuple]:
        """Find swing lows: (index, price, timestamp)"""
        swings = []
        lows = ohlc['low'].values
        n = self.swing_length
        
        for i in range(n, len(ohlc) - n):
            if lows[i] == min(lows[i-n:i+n+1]):
                swings.append((i, lows[i], ohlc.index[i]))
        
        return swings
    
    def _find_equal_levels(
        self, 
        swings: List[tuple], 
        level_type: str,
        ohlc: pd.DataFrame
    ) -> List[EqualLevel]:
        """Group swings that are at similar prices into equal levels"""
        if len(swings) < 2:
            return []
        
        tolerance = self.tolerance_pips * self.pip_size
        equal_levels = []
        used = set()
        
        for i, (idx1, price1, ts1) in enumerate(swings):
            if i in used:
                continue
            
            # Find all swings at similar price
            group = [(idx1, price1, ts1)]
            used.add(i)
            
            for j, (idx2, price2, ts2) in enumerate(swings):
                if j in used:
                    continue
                if abs(price1 - price2) <= tolerance:
                    group.append((idx2, price2, ts2))
                    used.add(j)
            
            if len(group) >= self.min_touches:
                prices = [g[1] for g in group]
                timestamps = [g[2] for g in group]
                equal_levels.append(EqualLevel(
                    prices=prices,
                    avg_price=sum(prices) / len(prices),
                    type=level_type,
                    touches=len(group),
                    timestamps=timestamps
                ))
        
        return equal_levels
    
    def _build_liquidity_pools(
        self,
        swings: List[tuple],
        equal_levels: List[EqualLevel],
        pool_type: str,
        ohlc: pd.DataFrame
    ) -> List[LiquidityPool]:
        """Build comprehensive liquidity pool list"""
        pools = []
        equal_prices = set()
        
        # Add equal levels as strong pools
        for el in equal_levels:
            equal_prices.add(round(el.avg_price, 5))
            pools.append(LiquidityPool(
                price=el.avg_price,
                type=pool_type,
                strength="STRONG",
                is_equal_level=True,
                touches=el.touches,
                swept=el.swept
            ))
        
        # Add single swing points as weaker pools
        for idx, price, ts in swings:
            if round(price, 5) not in equal_prices:
                pools.append(LiquidityPool(
                    price=price,
                    type=pool_type,
                    strength="WEAK",
                    is_equal_level=False,
                    touches=1,
                    swept=False
                ))
        
        return sorted(pools, key=lambda x: x.price, reverse=(pool_type == "BSL"))
    
    def get_nearest_bsl(self, price: float, pools: List[LiquidityPool]) -> Optional[LiquidityPool]:
        """Get nearest unswept BSL above current price"""
        above = [p for p in pools if p.type == "BSL" and p.price > price and not p.swept]
        if above:
            return min(above, key=lambda x: x.price)
        return None
    
    def get_nearest_ssl(self, price: float, pools: List[LiquidityPool]) -> Optional[LiquidityPool]:
        """Get nearest unswept SSL below current price"""
        below = [p for p in pools if p.type == "SSL" and p.price < price and not p.swept]
        if below:
            return max(below, key=lambda x: x.price)
        return None

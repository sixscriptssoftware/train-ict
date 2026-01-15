"""Liquidity Detection Module

Detects buy-side and sell-side liquidity pools, equal highs/lows,
and liquidity sweeps.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import numpy as np


class LiquidityType(Enum):
    BUY_SIDE = 1
    SELL_SIDE = -1


@dataclass
class LiquidityPool:
    """Represents a liquidity pool (cluster of stops)"""
    index: int
    timestamp: pd.Timestamp
    level: float
    liquidity_type: LiquidityType
    strength: int
    is_equal_level: bool
    swept: bool = False
    sweep_index: Optional[int] = None


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep event"""
    index: int
    timestamp: pd.Timestamp
    liquidity_type: LiquidityType
    swept_level: float
    sweep_high: float
    sweep_low: float
    is_rejection: bool


class LiquidityDetector:
    """
    Detects liquidity pools and sweeps.
    
    Liquidity Concepts:
    - Buy-Side Liquidity (BSL): Stop orders above swing highs
    - Sell-Side Liquidity (SSL): Stop orders below swing lows
    - Equal Highs/Lows: Multiple touches at same level = strong liquidity
    - Sweeps: When price takes out liquidity and reverses
    
    ICT teaches that price is "drawn" to liquidity.
    """
    
    def __init__(
        self,
        swing_length: int = 10,
        equal_level_tolerance: float = 0.0002,
        sweep_confirmation_candles: int = 3,
    ):
        self.swing_length = swing_length
        self.equal_level_tolerance = equal_level_tolerance
        self.sweep_confirmation_candles = sweep_confirmation_candles
        self._pools: list[LiquidityPool] = []
        self._sweeps: list[LiquiditySweep] = []
    
    def detect(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """
        Detect liquidity pools and sweeps.
        
        Returns:
            DataFrame with liquidity information for each bar
        """
        if len(ohlc) < self.swing_length * 2:
            return self._empty_result(ohlc)
        
        result = pd.DataFrame(index=ohlc.index)
        result["liquidity_type"] = 0
        result["liquidity_level"] = np.nan
        result["liquidity_strength"] = 0
        result["is_equal_level"] = False
        result["is_sweep"] = False
        result["sweep_type"] = 0
        
        self._pools = []
        self._sweeps = []
        
        self._detect_swing_liquidity(ohlc, result)
        self._detect_equal_levels(ohlc, result)
        self._detect_sweeps(ohlc, result)
        
        return result
    
    def _detect_swing_liquidity(
        self, ohlc: pd.DataFrame, result: pd.DataFrame
    ) -> None:
        """Detect liquidity at swing highs and lows"""
        n = self.swing_length
        
        for i in range(n, len(ohlc) - n):
            high = ohlc.iloc[i]["high"]
            low = ohlc.iloc[i]["low"]
            
            left_highs = ohlc.iloc[i - n : i]["high"].values
            right_highs = ohlc.iloc[i + 1 : i + n + 1]["high"].values
            
            if high > max(left_highs) and high > max(right_highs):
                pool = LiquidityPool(
                    index=i,
                    timestamp=ohlc.index[i],
                    level=high,
                    liquidity_type=LiquidityType.BUY_SIDE,
                    strength=1,
                    is_equal_level=False,
                )
                self._pools.append(pool)
                
                idx = ohlc.index[i]
                result.loc[idx, "liquidity_type"] = LiquidityType.BUY_SIDE.value
                result.loc[idx, "liquidity_level"] = high
                result.loc[idx, "liquidity_strength"] = 1
            
            left_lows = ohlc.iloc[i - n : i]["low"].values
            right_lows = ohlc.iloc[i + 1 : i + n + 1]["low"].values
            
            if low < min(left_lows) and low < min(right_lows):
                pool = LiquidityPool(
                    index=i,
                    timestamp=ohlc.index[i],
                    level=low,
                    liquidity_type=LiquidityType.SELL_SIDE,
                    strength=1,
                    is_equal_level=False,
                )
                self._pools.append(pool)
                
                idx = ohlc.index[i]
                result.loc[idx, "liquidity_type"] = LiquidityType.SELL_SIDE.value
                result.loc[idx, "liquidity_level"] = low
                result.loc[idx, "liquidity_strength"] = 1
    
    def _detect_equal_levels(
        self, ohlc: pd.DataFrame, result: pd.DataFrame
    ) -> None:
        """Detect equal highs and equal lows (strong liquidity)"""
        bsl_pools = [p for p in self._pools if p.liquidity_type == LiquidityType.BUY_SIDE]
        ssl_pools = [p for p in self._pools if p.liquidity_type == LiquidityType.SELL_SIDE]
        
        for pool in bsl_pools:
            matches = [
                p for p in bsl_pools
                if p != pool
                and abs(p.level - pool.level) <= self.equal_level_tolerance
            ]
            if matches:
                pool.is_equal_level = True
                pool.strength = len(matches) + 1
                result.loc[pool.timestamp, "is_equal_level"] = True
                result.loc[pool.timestamp, "liquidity_strength"] = pool.strength
        
        for pool in ssl_pools:
            matches = [
                p for p in ssl_pools
                if p != pool
                and abs(p.level - pool.level) <= self.equal_level_tolerance
            ]
            if matches:
                pool.is_equal_level = True
                pool.strength = len(matches) + 1
                result.loc[pool.timestamp, "is_equal_level"] = True
                result.loc[pool.timestamp, "liquidity_strength"] = pool.strength
    
    def _detect_sweeps(self, ohlc: pd.DataFrame, result: pd.DataFrame) -> None:
        """Detect when price sweeps liquidity and reverses"""
        for pool in self._pools:
            if pool.swept:
                continue
            
            for i in range(pool.index + 1, len(ohlc)):
                candle = ohlc.iloc[i]
                
                if pool.liquidity_type == LiquidityType.BUY_SIDE:
                    if candle["high"] > pool.level:
                        is_rejection = self._check_rejection(
                            ohlc, i, pool.level, is_bsl=True
                        )
                        
                        pool.swept = True
                        pool.sweep_index = i
                        
                        sweep = LiquiditySweep(
                            index=i,
                            timestamp=ohlc.index[i],
                            liquidity_type=LiquidityType.BUY_SIDE,
                            swept_level=pool.level,
                            sweep_high=candle["high"],
                            sweep_low=candle["low"],
                            is_rejection=is_rejection,
                        )
                        self._sweeps.append(sweep)
                        
                        result.loc[ohlc.index[i], "is_sweep"] = True
                        result.loc[ohlc.index[i], "sweep_type"] = LiquidityType.BUY_SIDE.value
                        break
                
                elif pool.liquidity_type == LiquidityType.SELL_SIDE:
                    if candle["low"] < pool.level:
                        is_rejection = self._check_rejection(
                            ohlc, i, pool.level, is_bsl=False
                        )
                        
                        pool.swept = True
                        pool.sweep_index = i
                        
                        sweep = LiquiditySweep(
                            index=i,
                            timestamp=ohlc.index[i],
                            liquidity_type=LiquidityType.SELL_SIDE,
                            swept_level=pool.level,
                            sweep_high=candle["high"],
                            sweep_low=candle["low"],
                            is_rejection=is_rejection,
                        )
                        self._sweeps.append(sweep)
                        
                        result.loc[ohlc.index[i], "is_sweep"] = True
                        result.loc[ohlc.index[i], "sweep_type"] = LiquidityType.SELL_SIDE.value
                        break
    
    def _check_rejection(
        self, ohlc: pd.DataFrame, sweep_index: int, level: float, is_bsl: bool
    ) -> bool:
        """Check if price rejected after sweeping liquidity"""
        if sweep_index + self.sweep_confirmation_candles >= len(ohlc):
            return False
        
        sweep_candle = ohlc.iloc[sweep_index]
        
        if is_bsl:
            closes_below = all(
                ohlc.iloc[i]["close"] < level
                for i in range(sweep_index, min(sweep_index + self.sweep_confirmation_candles, len(ohlc)))
            )
            return closes_below and sweep_candle["close"] < sweep_candle["open"]
        else:
            closes_above = all(
                ohlc.iloc[i]["close"] > level
                for i in range(sweep_index, min(sweep_index + self.sweep_confirmation_candles, len(ohlc)))
            )
            return closes_above and sweep_candle["close"] > sweep_candle["open"]
    
    def _empty_result(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Return empty result DataFrame"""
        result = pd.DataFrame(index=ohlc.index)
        result["liquidity_type"] = 0
        result["liquidity_level"] = np.nan
        result["liquidity_strength"] = 0
        result["is_equal_level"] = False
        result["is_sweep"] = False
        result["sweep_type"] = 0
        return result
    
    def get_active_liquidity(
        self, liquidity_type: Optional[LiquidityType] = None
    ) -> list[LiquidityPool]:
        """Get all unswept liquidity pools"""
        active = [p for p in self._pools if not p.swept]
        if liquidity_type:
            active = [p for p in active if p.liquidity_type == liquidity_type]
        return active
    
    def get_nearest_liquidity(
        self, price: float, liquidity_type: LiquidityType
    ) -> Optional[LiquidityPool]:
        """Get nearest unswept liquidity to price"""
        active = self.get_active_liquidity(liquidity_type)
        if not active:
            return None
        
        if liquidity_type == LiquidityType.BUY_SIDE:
            above = [p for p in active if p.level > price]
            if above:
                return min(above, key=lambda p: p.level)
        else:
            below = [p for p in active if p.level < price]
            if below:
                return max(below, key=lambda p: p.level)
        
        return None
    
    def get_recent_sweeps(self, count: int = 5) -> list[LiquiditySweep]:
        """Get most recent liquidity sweeps"""
        return sorted(self._sweeps, key=lambda s: s.index, reverse=True)[:count]

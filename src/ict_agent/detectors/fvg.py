"""Fair Value Gap (FVG) Detection Module

Detects imbalances in price where Smart Money has left gaps due to aggressive
institutional order flow.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import numpy as np


class FVGDirection(Enum):
    BULLISH = 1
    BEARISH = -1


@dataclass
class FVG:
    """Represents a Fair Value Gap"""
    index: int
    direction: FVGDirection
    top: float
    bottom: float
    midpoint: float
    ote_62: float
    ote_705: float
    ote_79: float
    size: float
    timestamp: pd.Timestamp
    mitigated: bool = False
    mitigation_index: Optional[int] = None
    
    @property
    def is_valid(self) -> bool:
        return not self.mitigated
    
    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top
    
    def get_entry_level(self, level: str = "midpoint") -> float:
        levels = {
            "midpoint": self.midpoint,
            "ote_62": self.ote_62,
            "ote_705": self.ote_705,
            "ote_79": self.ote_79,
        }
        return levels.get(level, self.midpoint)


class FVGDetector:
    """
    Detects Fair Value Gaps in OHLCV data.
    
    FVG Formation Rules:
    - Bullish: Gap between candle[i-2].high and candle[i].low
    - Bearish: Gap between candle[i-2].low and candle[i].high
    
    Must follow displacement (strong institutional candle).
    """
    
    def __init__(
        self,
        min_gap_pips: float = 5.0,
        pip_size: float = 0.0001,
        join_consecutive: bool = False,
    ):
        self.min_gap_pips = min_gap_pips
        self.pip_size = pip_size
        self.join_consecutive = join_consecutive
        self._fvgs: list[FVG] = []
    
    def detect(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """
        Detect all FVGs in the given OHLC data.
        
        Args:
            ohlc: DataFrame with columns ['open', 'high', 'low', 'close']
                  and DatetimeIndex
        
        Returns:
            DataFrame with FVG information for each bar
        """
        if len(ohlc) < 3:
            return self._empty_result(ohlc)
        
        result = pd.DataFrame(index=ohlc.index)
        result["fvg_direction"] = 0
        result["fvg_top"] = np.nan
        result["fvg_bottom"] = np.nan
        result["fvg_midpoint"] = np.nan
        result["fvg_mitigated"] = False
        result["fvg_mitigation_index"] = np.nan
        
        self._fvgs = []
        
        for i in range(2, len(ohlc)):
            candle_prev2 = ohlc.iloc[i - 2]
            candle_current = ohlc.iloc[i]
            candle_mid = ohlc.iloc[i - 1]
            
            bullish_fvg = self._check_bullish_fvg(candle_prev2, candle_current, candle_mid)
            if bullish_fvg:
                self._record_fvg(result, ohlc, i, FVGDirection.BULLISH, bullish_fvg)
                continue
            
            bearish_fvg = self._check_bearish_fvg(candle_prev2, candle_current, candle_mid)
            if bearish_fvg:
                self._record_fvg(result, ohlc, i, FVGDirection.BEARISH, bearish_fvg)
        
        self._check_mitigation(ohlc, result)
        
        if self.join_consecutive:
            result = self._join_consecutive_fvgs(result)
        
        return result
    
    def _check_bullish_fvg(
        self, prev2: pd.Series, current: pd.Series, mid: pd.Series
    ) -> Optional[tuple[float, float]]:
        """Check for bullish FVG (gap up with displacement)"""
        gap_bottom = prev2["high"]
        gap_top = current["low"]
        
        if gap_top > gap_bottom:
            gap_size = gap_top - gap_bottom
            min_gap = self.min_gap_pips * self.pip_size
            
            mid_body = abs(mid["close"] - mid["open"])
            is_displacement = mid["close"] > mid["open"] and mid_body > 0
            
            if gap_size >= min_gap and is_displacement:
                return (gap_top, gap_bottom)
        
        return None
    
    def _check_bearish_fvg(
        self, prev2: pd.Series, current: pd.Series, mid: pd.Series
    ) -> Optional[tuple[float, float]]:
        """Check for bearish FVG (gap down with displacement)"""
        gap_top = prev2["low"]
        gap_bottom = current["high"]
        
        if gap_top > gap_bottom:
            gap_size = gap_top - gap_bottom
            min_gap = self.min_gap_pips * self.pip_size
            
            mid_body = abs(mid["close"] - mid["open"])
            is_displacement = mid["close"] < mid["open"] and mid_body > 0
            
            if gap_size >= min_gap and is_displacement:
                return (gap_top, gap_bottom)
        
        return None
    
    def _record_fvg(
        self,
        result: pd.DataFrame,
        ohlc: pd.DataFrame,
        index: int,
        direction: FVGDirection,
        gap: tuple[float, float],
    ) -> None:
        """Record FVG in result DataFrame and internal list"""
        top, bottom = gap
        size = top - bottom
        midpoint = (top + bottom) / 2
        
        if direction == FVGDirection.BULLISH:
            ote_62 = bottom + (size * 0.382)
            ote_705 = bottom + (size * 0.295)
            ote_79 = bottom + (size * 0.21)
        else:
            ote_62 = top - (size * 0.382)
            ote_705 = top - (size * 0.295)
            ote_79 = top - (size * 0.21)
        
        idx = ohlc.index[index]
        result.loc[idx, "fvg_direction"] = direction.value
        result.loc[idx, "fvg_top"] = top
        result.loc[idx, "fvg_bottom"] = bottom
        result.loc[idx, "fvg_midpoint"] = midpoint
        
        fvg = FVG(
            index=index,
            direction=direction,
            top=top,
            bottom=bottom,
            midpoint=midpoint,
            ote_62=ote_62,
            ote_705=ote_705,
            ote_79=ote_79,
            size=size,
            timestamp=idx,
        )
        self._fvgs.append(fvg)
    
    def _check_mitigation(self, ohlc: pd.DataFrame, result: pd.DataFrame) -> None:
        """Check if FVGs have been mitigated (price traded through them)"""
        for fvg in self._fvgs:
            for i in range(fvg.index + 1, len(ohlc)):
                candle = ohlc.iloc[i]
                
                if fvg.direction == FVGDirection.BULLISH:
                    if candle["low"] <= fvg.bottom:
                        fvg.mitigated = True
                        fvg.mitigation_index = i
                        result.loc[fvg.timestamp, "fvg_mitigated"] = True
                        result.loc[fvg.timestamp, "fvg_mitigation_index"] = i
                        break
                else:
                    if candle["high"] >= fvg.top:
                        fvg.mitigated = True
                        fvg.mitigation_index = i
                        result.loc[fvg.timestamp, "fvg_mitigated"] = True
                        result.loc[fvg.timestamp, "fvg_mitigation_index"] = i
                        break
    
    def _join_consecutive_fvgs(self, result: pd.DataFrame) -> pd.DataFrame:
        """Join consecutive FVGs of same direction into single larger FVG"""
        return result
    
    def _empty_result(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Return empty result DataFrame"""
        result = pd.DataFrame(index=ohlc.index)
        result["fvg_direction"] = 0
        result["fvg_top"] = np.nan
        result["fvg_bottom"] = np.nan
        result["fvg_midpoint"] = np.nan
        result["fvg_mitigated"] = False
        result["fvg_mitigation_index"] = np.nan
        return result
    
    def get_active_fvgs(self, direction: Optional[FVGDirection] = None) -> list[FVG]:
        """Get all unmitigated FVGs, optionally filtered by direction"""
        active = [f for f in self._fvgs if not f.mitigated]
        if direction:
            active = [f for f in active if f.direction == direction]
        return active
    
    def get_nearest_fvg(
        self, price: float, direction: FVGDirection
    ) -> Optional[FVG]:
        """Get the nearest unmitigated FVG to the given price"""
        active = self.get_active_fvgs(direction)
        if not active:
            return None
        
        if direction == FVGDirection.BULLISH:
            below = [f for f in active if f.top < price]
            if below:
                return max(below, key=lambda f: f.top)
        else:
            above = [f for f in active if f.bottom > price]
            if above:
                return min(above, key=lambda f: f.bottom)
        
        return None

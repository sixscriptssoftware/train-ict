"""Displacement Detection Module

Detects displacement - strong, impulsive price moves that indicate
institutional order flow.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import numpy as np


class DisplacementDirection(Enum):
    BULLISH = 1
    BEARISH = -1


@dataclass
class Displacement:
    """Represents a displacement candle/move"""
    index: int
    timestamp: pd.Timestamp
    direction: DisplacementDirection
    open_price: float
    close_price: float
    high: float
    low: float
    body_size: float
    range_size: float
    body_ratio: float
    atr_multiple: float


class DisplacementDetector:
    """
    Detects displacement - the footprint of institutional order flow.
    
    Displacement Characteristics:
    - Long-bodied candle(s)
    - Little to no wick on opposite end
    - Violent assertion of control
    
    ICT Rule: Without displacement, any break or setup should be IGNORED.
    """
    
    def __init__(
        self,
        atr_period: int = 14,
        min_atr_multiple: float = 1.5,
        min_body_ratio: float = 0.6,
    ):
        self.atr_period = atr_period
        self.min_atr_multiple = min_atr_multiple
        self.min_body_ratio = min_body_ratio
        self._displacements: list[Displacement] = []
    
    def detect(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """
        Detect displacement candles in OHLC data.
        
        Returns:
            DataFrame with displacement information for each bar
        """
        if len(ohlc) < self.atr_period + 1:
            return self._empty_result(ohlc)
        
        result = pd.DataFrame(index=ohlc.index)
        result["is_displacement"] = False
        result["displacement_direction"] = 0
        result["body_size"] = 0.0
        result["atr_multiple"] = 0.0
        result["body_ratio"] = 0.0
        
        self._displacements = []
        atr = self._calculate_atr(ohlc)
        
        for i in range(self.atr_period, len(ohlc)):
            candle = ohlc.iloc[i]
            current_atr = atr.iloc[i]
            
            if pd.isna(current_atr) or current_atr == 0:
                continue
            
            body_size = abs(candle["close"] - candle["open"])
            range_size = candle["high"] - candle["low"]
            
            if range_size == 0:
                continue
            
            body_ratio = body_size / range_size
            atr_multiple = range_size / current_atr
            
            is_displacement = (
                atr_multiple >= self.min_atr_multiple
                and body_ratio >= self.min_body_ratio
            )
            
            if is_displacement:
                direction = (
                    DisplacementDirection.BULLISH
                    if candle["close"] > candle["open"]
                    else DisplacementDirection.BEARISH
                )
                
                displacement = Displacement(
                    index=i,
                    timestamp=ohlc.index[i],
                    direction=direction,
                    open_price=candle["open"],
                    close_price=candle["close"],
                    high=candle["high"],
                    low=candle["low"],
                    body_size=body_size,
                    range_size=range_size,
                    body_ratio=body_ratio,
                    atr_multiple=atr_multiple,
                )
                self._displacements.append(displacement)
                
                idx = ohlc.index[i]
                result.loc[idx, "is_displacement"] = True
                result.loc[idx, "displacement_direction"] = direction.value
                result.loc[idx, "body_size"] = body_size
                result.loc[idx, "atr_multiple"] = atr_multiple
                result.loc[idx, "body_ratio"] = body_ratio
        
        return result
    
    def _calculate_atr(self, ohlc: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high = ohlc["high"]
        low = ohlc["low"]
        close = ohlc["close"].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=self.atr_period).mean()
    
    def _empty_result(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Return empty result DataFrame"""
        result = pd.DataFrame(index=ohlc.index)
        result["is_displacement"] = False
        result["displacement_direction"] = 0
        result["body_size"] = 0.0
        result["atr_multiple"] = 0.0
        result["body_ratio"] = 0.0
        return result
    
    def get_displacements(
        self, direction: Optional[DisplacementDirection] = None
    ) -> list[Displacement]:
        """Get all detected displacements"""
        if direction:
            return [d for d in self._displacements if d.direction == direction]
        return self._displacements
    
    def get_recent_displacement(
        self, direction: Optional[DisplacementDirection] = None
    ) -> Optional[Displacement]:
        """Get most recent displacement"""
        displacements = self.get_displacements(direction)
        return displacements[-1] if displacements else None
    
    def has_displacement_after(
        self,
        index: int,
        direction: DisplacementDirection,
        within_candles: int = 3,
    ) -> bool:
        """Check if displacement occurred within N candles after given index"""
        for d in self._displacements:
            if d.direction == direction:
                if index < d.index <= index + within_candles:
                    return True
        return False

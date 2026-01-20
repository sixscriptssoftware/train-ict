"""
ICT Candle Pattern Detectors

- Displacement Candle (big body, small wicks)
- Engulfing at key levels
- Wick Rejection into PD Array
- SMC Candle (sweep + close back inside)
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
import pandas as pd
import numpy as np


@dataclass
class DisplacementCandle:
    """
    Displacement = Strong institutional move
    - Large body relative to ATR
    - Small wicks (body > 70% of total range)
    - Shows conviction
    """
    index: int
    timestamp: pd.Timestamp
    direction: Literal["BULLISH", "BEARISH"]
    body_size: float
    total_range: float
    body_percentage: float  # Body as % of total range
    atr_multiple: float  # How many ATRs is this candle
    open: float
    close: float
    high: float
    low: float


@dataclass
class EngulfingCandle:
    """
    Engulfing pattern - reversal signal at key levels
    """
    index: int
    timestamp: pd.Timestamp
    direction: Literal["BULLISH", "BEARISH"]
    engulfing_body: float
    engulfed_body: float
    at_key_level: bool
    level_type: str  # "FVG", "OB", "LIQUIDITY", etc.


@dataclass
class WickRejection:
    """
    Wick rejection - price rejected from a level
    Long wick shows rejection/absorption of orders
    """
    index: int
    timestamp: pd.Timestamp
    direction: Literal["BULLISH", "BEARISH"]  # Direction of the rejection (where price is heading)
    wick_size: float
    body_size: float
    wick_ratio: float  # Wick as multiple of body
    rejection_price: float
    rejection_level_type: str  # What was rejected at


@dataclass
class SMCCandle:
    """
    Smart Money Concept candle
    - Sweeps liquidity then closes back inside range
    - Shows stop hunt + reversal
    """
    index: int
    timestamp: pd.Timestamp
    direction: Literal["BULLISH", "BEARISH"]
    sweep_price: float  # The extreme that swept
    close_price: float  # Where it closed (back inside)
    level_swept: float
    

class CandlePatternDetector:
    """
    Detects ICT candle patterns.
    
    Key patterns:
    1. Displacement - Shows institutional intent
    2. Engulfing - Reversal at key levels
    3. Wick Rejection - Shows absorption/rejection
    4. SMC Candle - Sweep + close back (manipulation)
    """
    
    def __init__(
        self,
        atr_period: int = 14,
        displacement_atr_mult: float = 1.5,
        displacement_body_pct: float = 70.0,
        wick_rejection_ratio: float = 2.0,
        pip_size: float = 0.0001
    ):
        self.atr_period = atr_period
        self.displacement_atr_mult = displacement_atr_mult
        self.displacement_body_pct = displacement_body_pct
        self.wick_rejection_ratio = wick_rejection_ratio
        self.pip_size = pip_size
    
    def detect(self, ohlc: pd.DataFrame, key_levels: List[float] = None) -> dict:
        """
        Detect all candle patterns.
        
        Args:
            ohlc: OHLC DataFrame
            key_levels: Optional list of important price levels (for engulfing/rejection detection)
        
        Returns:
            {
                'displacements': List[DisplacementCandle],
                'engulfings': List[EngulfingCandle],
                'wick_rejections': List[WickRejection],
                'smc_candles': List[SMCCandle],
                'recent_displacement': Optional[DisplacementCandle],
            }
        """
        # Calculate ATR
        atr = self._calculate_atr(ohlc)
        
        displacements = []
        engulfings = []
        wick_rejections = []
        smc_candles = []
        
        if key_levels is None:
            key_levels = []
        
        for i in range(1, len(ohlc)):
            candle = ohlc.iloc[i]
            prev_candle = ohlc.iloc[i-1]
            current_atr = atr.iloc[i] if i < len(atr) else atr.iloc[-1]
            
            # === DISPLACEMENT ===
            displacement = self._check_displacement(i, candle, current_atr, ohlc.index[i])
            if displacement:
                displacements.append(displacement)
            
            # === ENGULFING ===
            engulfing = self._check_engulfing(i, candle, prev_candle, key_levels, ohlc.index[i])
            if engulfing:
                engulfings.append(engulfing)
            
            # === WICK REJECTION ===
            rejection = self._check_wick_rejection(i, candle, key_levels, ohlc.index[i])
            if rejection:
                wick_rejections.append(rejection)
            
            # === SMC CANDLE ===
            # Need previous swings for this - simplified version
            if i >= 10:
                smc = self._check_smc_candle(i, candle, ohlc.iloc[i-10:i], ohlc.index[i])
                if smc:
                    smc_candles.append(smc)
        
        return {
            'displacements': displacements,
            'engulfings': engulfings,
            'wick_rejections': wick_rejections,
            'smc_candles': smc_candles,
            'recent_displacement': displacements[-1] if displacements else None,
        }
    
    def _calculate_atr(self, ohlc: pd.DataFrame) -> pd.Series:
        """Calculate ATR"""
        high = ohlc['high']
        low = ohlc['low']
        close = ohlc['close'].shift(1)
        
        tr = pd.concat([
            high - low,
            (high - close).abs(),
            (low - close).abs()
        ], axis=1).max(axis=1)
        
        return tr.rolling(self.atr_period).mean()
    
    def _check_displacement(
        self, 
        index: int, 
        candle: pd.Series, 
        atr: float,
        timestamp: pd.Timestamp
    ) -> Optional[DisplacementCandle]:
        """Check if candle is a displacement candle"""
        body = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']
        
        if total_range == 0:
            return None
        
        body_pct = (body / total_range) * 100
        atr_mult = total_range / atr if atr > 0 else 0
        
        # Displacement criteria: large body (>70% of range) AND > 1.5x ATR
        if body_pct >= self.displacement_body_pct and atr_mult >= self.displacement_atr_mult:
            direction = "BULLISH" if candle['close'] > candle['open'] else "BEARISH"
            
            return DisplacementCandle(
                index=index,
                timestamp=timestamp,
                direction=direction,
                body_size=body,
                total_range=total_range,
                body_percentage=body_pct,
                atr_multiple=atr_mult,
                open=candle['open'],
                close=candle['close'],
                high=candle['high'],
                low=candle['low']
            )
        
        return None
    
    def _check_engulfing(
        self,
        index: int,
        candle: pd.Series,
        prev_candle: pd.Series,
        key_levels: List[float],
        timestamp: pd.Timestamp
    ) -> Optional[EngulfingCandle]:
        """Check for engulfing pattern"""
        curr_body = abs(candle['close'] - candle['open'])
        prev_body = abs(prev_candle['close'] - prev_candle['open'])
        
        curr_bullish = candle['close'] > candle['open']
        prev_bullish = prev_candle['close'] > prev_candle['open']
        
        # Engulfing = opposite direction AND current body larger
        if curr_bullish != prev_bullish and curr_body > prev_body:
            # Check if current candle's body engulfs previous candle's body
            if curr_bullish:
                engulfs = candle['open'] <= prev_candle['close'] and candle['close'] >= prev_candle['open']
            else:
                engulfs = candle['open'] >= prev_candle['close'] and candle['close'] <= prev_candle['open']
            
            if engulfs:
                # Check if at key level
                at_level = False
                level_type = ""
                for level in key_levels:
                    if abs(candle['low'] - level) < 10 * self.pip_size or abs(candle['high'] - level) < 10 * self.pip_size:
                        at_level = True
                        level_type = "KEY_LEVEL"
                        break
                
                return EngulfingCandle(
                    index=index,
                    timestamp=timestamp,
                    direction="BULLISH" if curr_bullish else "BEARISH",
                    engulfing_body=curr_body,
                    engulfed_body=prev_body,
                    at_key_level=at_level,
                    level_type=level_type
                )
        
        return None
    
    def _check_wick_rejection(
        self,
        index: int,
        candle: pd.Series,
        key_levels: List[float],
        timestamp: pd.Timestamp
    ) -> Optional[WickRejection]:
        """Check for wick rejection pattern"""
        body = abs(candle['close'] - candle['open'])
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        
        if body == 0:
            body = 0.00001  # Avoid division by zero
        
        # Check upper wick rejection (bearish signal)
        if upper_wick > body * self.wick_rejection_ratio:
            level_type = ""
            for level in key_levels:
                if abs(candle['high'] - level) < 5 * self.pip_size:
                    level_type = "KEY_LEVEL"
                    break
            
            return WickRejection(
                index=index,
                timestamp=timestamp,
                direction="BEARISH",
                wick_size=upper_wick,
                body_size=body,
                wick_ratio=upper_wick / body,
                rejection_price=candle['high'],
                rejection_level_type=level_type
            )
        
        # Check lower wick rejection (bullish signal)
        if lower_wick > body * self.wick_rejection_ratio:
            level_type = ""
            for level in key_levels:
                if abs(candle['low'] - level) < 5 * self.pip_size:
                    level_type = "KEY_LEVEL"
                    break
            
            return WickRejection(
                index=index,
                timestamp=timestamp,
                direction="BULLISH",
                wick_size=lower_wick,
                body_size=body,
                wick_ratio=lower_wick / body,
                rejection_price=candle['low'],
                rejection_level_type=level_type
            )
        
        return None
    
    def _check_smc_candle(
        self,
        index: int,
        candle: pd.Series,
        recent_candles: pd.DataFrame,
        timestamp: pd.Timestamp
    ) -> Optional[SMCCandle]:
        """Check for SMC candle (sweep + close back inside)"""
        recent_high = recent_candles['high'].max()
        recent_low = recent_candles['low'].min()
        
        # Check if candle swept high then closed back inside
        if candle['high'] > recent_high and candle['close'] < recent_high:
            return SMCCandle(
                index=index,
                timestamp=timestamp,
                direction="BEARISH",
                sweep_price=candle['high'],
                close_price=candle['close'],
                level_swept=recent_high
            )
        
        # Check if candle swept low then closed back inside
        if candle['low'] < recent_low and candle['close'] > recent_low:
            return SMCCandle(
                index=index,
                timestamp=timestamp,
                direction="BULLISH",
                sweep_price=candle['low'],
                close_price=candle['close'],
                level_swept=recent_low
            )
        
        return None

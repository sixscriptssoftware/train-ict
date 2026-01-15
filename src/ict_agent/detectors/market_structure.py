"""Market Structure Analysis Module

Detects swing highs/lows, Break of Structure (BOS), Shift in Market Structure (SMS),
and Change of Character (CHoCH).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import pandas as pd
import numpy as np


class StructureType(Enum):
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


class SwingType(Enum):
    HIGH = 1
    LOW = -1


class BreakType(Enum):
    BOS = "bos"
    SMS = "sms"
    CHOCH = "choch"


@dataclass
class SwingPoint:
    """Represents a swing high or low"""
    index: int
    timestamp: pd.Timestamp
    price: float
    swing_type: SwingType
    is_protected: bool = True
    broken: bool = False
    broken_by: Optional[int] = None


@dataclass
class StructureBreak:
    """Represents a structure break (BOS, SMS, or CHoCH)"""
    index: int
    timestamp: pd.Timestamp
    break_type: BreakType
    direction: StructureType
    broken_swing: SwingPoint
    break_price: float
    has_displacement: bool


@dataclass
class MarketStructure:
    """Current market structure state"""
    trend: StructureType
    last_hh: Optional[SwingPoint] = None
    last_hl: Optional[SwingPoint] = None
    last_lh: Optional[SwingPoint] = None
    last_ll: Optional[SwingPoint] = None
    swing_sequence: list[SwingPoint] = field(default_factory=list)


class MarketStructureAnalyzer:
    """
    Analyzes market structure to identify:
    - Swing highs and lows
    - Higher highs (HH), Higher lows (HL), Lower highs (LH), Lower lows (LL)
    - Break of Structure (BOS) - continuation
    - Shift in Market Structure (SMS/MSS) - reversal
    - Change of Character (CHoCH) - early reversal warning
    
    Core ICT Rule: Structure breaks only valid with DISPLACEMENT
    """
    
    def __init__(
        self,
        swing_length: int = 10,
        require_displacement: bool = True,
        displacement_atr_mult: float = 1.5,
    ):
        self.swing_length = swing_length
        self.require_displacement = require_displacement
        self.displacement_atr_mult = displacement_atr_mult
        
        self._swings: list[SwingPoint] = []
        self._breaks: list[StructureBreak] = []
        self._structure = MarketStructure(trend=StructureType.NEUTRAL)
    
    def analyze(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze market structure in OHLC data.
        
        Returns DataFrame with structure analysis for each bar.
        """
        if len(ohlc) < self.swing_length * 2 + 1:
            return self._empty_result(ohlc)
        
        result = pd.DataFrame(index=ohlc.index)
        result["swing_type"] = 0
        result["swing_level"] = np.nan
        result["structure_trend"] = 0
        result["break_type"] = ""
        result["break_direction"] = 0
        result["has_displacement"] = False
        
        atr = self._calculate_atr(ohlc)
        self._detect_swings(ohlc, result)
        self._analyze_structure(ohlc, result, atr)
        
        return result
    
    def _calculate_atr(self, ohlc: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range for displacement detection"""
        high = ohlc["high"]
        low = ohlc["low"]
        close = ohlc["close"].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def _detect_swings(self, ohlc: pd.DataFrame, result: pd.DataFrame) -> None:
        """Detect swing highs and lows"""
        self._swings = []
        n = self.swing_length
        
        for i in range(n, len(ohlc) - n):
            high = ohlc.iloc[i]["high"]
            low = ohlc.iloc[i]["low"]
            
            left_highs = ohlc.iloc[i - n : i]["high"].values
            right_highs = ohlc.iloc[i + 1 : i + n + 1]["high"].values
            
            if high > max(left_highs) and high > max(right_highs):
                swing = SwingPoint(
                    index=i,
                    timestamp=ohlc.index[i],
                    price=high,
                    swing_type=SwingType.HIGH,
                )
                self._swings.append(swing)
                result.loc[ohlc.index[i], "swing_type"] = SwingType.HIGH.value
                result.loc[ohlc.index[i], "swing_level"] = high
            
            left_lows = ohlc.iloc[i - n : i]["low"].values
            right_lows = ohlc.iloc[i + 1 : i + n + 1]["low"].values
            
            if low < min(left_lows) and low < min(right_lows):
                swing = SwingPoint(
                    index=i,
                    timestamp=ohlc.index[i],
                    price=low,
                    swing_type=SwingType.LOW,
                )
                self._swings.append(swing)
                result.loc[ohlc.index[i], "swing_type"] = SwingType.LOW.value
                result.loc[ohlc.index[i], "swing_level"] = low
    
    def _analyze_structure(
        self, ohlc: pd.DataFrame, result: pd.DataFrame, atr: pd.Series
    ) -> None:
        """Analyze structure breaks and trend direction"""
        self._breaks = []
        
        if len(self._swings) < 2:
            return
        
        swing_highs = [s for s in self._swings if s.swing_type == SwingType.HIGH]
        swing_lows = [s for s in self._swings if s.swing_type == SwingType.LOW]
        
        self._determine_initial_trend(swing_highs, swing_lows)
        
        for i in range(len(ohlc)):
            current_close = ohlc.iloc[i]["close"]
            current_high = ohlc.iloc[i]["high"]
            current_low = ohlc.iloc[i]["low"]
            current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0
            
            for swing in self._swings:
                if swing.broken or swing.index >= i:
                    continue
                
                if swing.swing_type == SwingType.HIGH and current_close > swing.price:
                    has_disp = self._check_displacement(
                        ohlc, i, swing.price, True, current_atr
                    )
                    
                    if not self.require_displacement or has_disp:
                        swing.broken = True
                        swing.broken_by = i
                        
                        break_type = self._classify_break(swing, True)
                        direction = StructureType.BULLISH
                        
                        structure_break = StructureBreak(
                            index=i,
                            timestamp=ohlc.index[i],
                            break_type=break_type,
                            direction=direction,
                            broken_swing=swing,
                            break_price=swing.price,
                            has_displacement=has_disp,
                        )
                        self._breaks.append(structure_break)
                        
                        result.loc[ohlc.index[i], "break_type"] = break_type.value
                        result.loc[ohlc.index[i], "break_direction"] = direction.value
                        result.loc[ohlc.index[i], "has_displacement"] = has_disp
                        
                        self._update_structure(swing, direction, swing_highs, swing_lows)
                
                elif swing.swing_type == SwingType.LOW and current_close < swing.price:
                    has_disp = self._check_displacement(
                        ohlc, i, swing.price, False, current_atr
                    )
                    
                    if not self.require_displacement or has_disp:
                        swing.broken = True
                        swing.broken_by = i
                        
                        break_type = self._classify_break(swing, False)
                        direction = StructureType.BEARISH
                        
                        structure_break = StructureBreak(
                            index=i,
                            timestamp=ohlc.index[i],
                            break_type=break_type,
                            direction=direction,
                            broken_swing=swing,
                            break_price=swing.price,
                            has_displacement=has_disp,
                        )
                        self._breaks.append(structure_break)
                        
                        result.loc[ohlc.index[i], "break_type"] = break_type.value
                        result.loc[ohlc.index[i], "break_direction"] = direction.value
                        result.loc[ohlc.index[i], "has_displacement"] = has_disp
                        
                        self._update_structure(swing, direction, swing_highs, swing_lows)
            
            result.loc[ohlc.index[i], "structure_trend"] = self._structure.trend.value
    
    def _check_displacement(
        self,
        ohlc: pd.DataFrame,
        index: int,
        level: float,
        bullish: bool,
        atr: float,
    ) -> bool:
        """Check if the break has displacement (institutional strength)"""
        if atr == 0:
            return True
        
        candle = ohlc.iloc[index]
        body = abs(candle["close"] - candle["open"])
        range_size = candle["high"] - candle["low"]
        
        is_strong_body = body > atr * self.displacement_atr_mult
        
        if bullish:
            is_bullish_candle = candle["close"] > candle["open"]
            broke_cleanly = candle["close"] > level
            return is_strong_body and is_bullish_candle and broke_cleanly
        else:
            is_bearish_candle = candle["close"] < candle["open"]
            broke_cleanly = candle["close"] < level
            return is_strong_body and is_bearish_candle and broke_cleanly
    
    def _classify_break(self, swing: SwingPoint, bullish_break: bool) -> BreakType:
        """Classify the break as BOS, SMS, or CHoCH"""
        current_trend = self._structure.trend
        
        if current_trend == StructureType.NEUTRAL:
            return BreakType.BOS
        
        if current_trend == StructureType.BULLISH:
            if bullish_break:
                return BreakType.BOS
            else:
                if swing.is_protected:
                    return BreakType.SMS
                return BreakType.CHOCH
        else:
            if not bullish_break:
                return BreakType.BOS
            else:
                if swing.is_protected:
                    return BreakType.SMS
                return BreakType.CHOCH
    
    def _determine_initial_trend(
        self, swing_highs: list[SwingPoint], swing_lows: list[SwingPoint]
    ) -> None:
        """Determine initial trend from swing sequence"""
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            recent_highs = sorted(swing_highs, key=lambda s: s.index)[-2:]
            recent_lows = sorted(swing_lows, key=lambda s: s.index)[-2:]
            
            hh = recent_highs[1].price > recent_highs[0].price
            hl = recent_lows[1].price > recent_lows[0].price
            
            if hh and hl:
                self._structure.trend = StructureType.BULLISH
            elif not hh and not hl:
                self._structure.trend = StructureType.BEARISH
    
    def _update_structure(
        self,
        broken_swing: SwingPoint,
        new_direction: StructureType,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> None:
        """Update internal structure state after a break"""
        old_trend = self._structure.trend
        
        if new_direction != old_trend and old_trend != StructureType.NEUTRAL:
            pass
        
        self._structure.trend = new_direction
        self._structure.swing_sequence.append(broken_swing)
    
    def _empty_result(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Return empty result DataFrame"""
        result = pd.DataFrame(index=ohlc.index)
        result["swing_type"] = 0
        result["swing_level"] = np.nan
        result["structure_trend"] = 0
        result["break_type"] = ""
        result["break_direction"] = 0
        result["has_displacement"] = False
        return result
    
    def get_current_trend(self) -> StructureType:
        """Get the current market structure trend"""
        return self._structure.trend
    
    def get_protected_swings(self) -> list[SwingPoint]:
        """Get all unbroken (protected) swing points"""
        return [s for s in self._swings if not s.broken]
    
    def get_latest_structure_break(self) -> Optional[StructureBreak]:
        """Get the most recent structure break"""
        return self._breaks[-1] if self._breaks else None

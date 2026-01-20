"""Enhanced Break of Structure (BOS) Detection

ICT-specific structure break detection with:
- BOS (Break of Structure) - trend continuation
- MSS/SMS (Market Structure Shift) - trend reversal
- CHoCH (Change of Character) - early reversal warning
- Displacement requirement for validity
- Internal vs External range context
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple
import pandas as pd
import numpy as np


class Trend(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class BreakType(Enum):
    BOS = "bos"          # Break of Structure - continuation
    MSS = "mss"          # Market Structure Shift - reversal
    CHOCH = "choch"      # Change of Character - early warning
    INTERNAL = "internal"  # Internal range break
    EXTERNAL = "external"  # External range break


@dataclass
class SwingPoint:
    """A swing high or low point."""
    price: float
    index: int
    timestamp: pd.Timestamp
    is_high: bool
    is_protected: bool = True
    broken_at: Optional[int] = None

    @property
    def swing_type(self) -> str:
        return "high" if self.is_high else "low"


@dataclass
class StructureBreakSignal:
    """A detected structure break."""
    break_type: BreakType
    direction: Trend
    break_time: pd.Timestamp
    break_index: int
    broken_level: float
    break_price: float
    has_displacement: bool
    displacement_size: float

    # Context
    previous_trend: Trend
    is_reversal: bool
    is_continuation: bool

    # Trade info
    entry_zone_top: Optional[float] = None
    entry_zone_bottom: Optional[float] = None
    stop_loss: Optional[float] = None

    # Metadata
    confidence: float = 0.0
    timeframe: str = ""
    symbol: str = ""
    notes: List[str] = field(default_factory=list)


class EnhancedStructureAnalyzer:
    """
    Enhanced market structure analyzer with ICT principles.

    ICT Rules:
    - Structure break MUST have displacement to be valid
    - BOS = continuation (breaks swing in trend direction)
    - MSS = reversal (breaks swing against trend with displacement)
    - CHoCH = early warning (internal structure break)

    Key Distinction:
    - Breaking a PROTECTED swing = MSS (major reversal)
    - Breaking an UNPROTECTED swing = BOS (continuation)
    """

    def __init__(
        self,
        swing_lookback: int = 10,
        require_displacement: bool = True,
        displacement_atr_mult: float = 1.5,
        pip_size: float = 0.0001,
    ):
        self.swing_lookback = swing_lookback
        self.require_displacement = require_displacement
        self.displacement_atr_mult = displacement_atr_mult
        self.pip_size = pip_size

        self._swings: List[SwingPoint] = []
        self._breaks: List[StructureBreakSignal] = []
        self._current_trend: Trend = Trend.NEUTRAL
        self._atr: Optional[pd.Series] = None

    def analyze(
        self,
        ohlc: pd.DataFrame,
        symbol: str = "",
        timeframe: str = "",
    ) -> List[StructureBreakSignal]:
        """
        Analyze market structure and detect breaks.

        Returns list of structure break signals.
        """
        if len(ohlc) < self.swing_lookback * 2 + 5:
            return []

        self._breaks = []
        self._calculate_atr(ohlc)
        self._find_swings(ohlc)
        self._determine_initial_trend()
        self._detect_breaks(ohlc, symbol, timeframe)

        return self._breaks

    def get_current_trend(self) -> Trend:
        """Get current market structure trend."""
        return self._current_trend

    def get_protected_swings(self) -> List[SwingPoint]:
        """Get all unbroken swing points."""
        return [s for s in self._swings if s.is_protected]

    def get_latest_break(self) -> Optional[StructureBreakSignal]:
        """Get most recent structure break."""
        return self._breaks[-1] if self._breaks else None

    def _calculate_atr(self, ohlc: pd.DataFrame, period: int = 14):
        high, low = ohlc["high"], ohlc["low"]
        close = ohlc["close"].shift(1)
        tr = pd.concat([high - low, abs(high - close), abs(low - close)], axis=1).max(axis=1)
        self._atr = tr.rolling(window=period).mean()

    def _find_swings(self, ohlc: pd.DataFrame):
        """Find all swing highs and lows."""
        self._swings = []
        n = self.swing_lookback

        for i in range(n, len(ohlc) - n):
            high = ohlc.iloc[i]["high"]
            low = ohlc.iloc[i]["low"]

            # Check for swing high
            left_highs = ohlc.iloc[i-n:i]["high"].values
            right_highs = ohlc.iloc[i+1:i+n+1]["high"].values

            if high > max(left_highs) and high > max(right_highs):
                self._swings.append(SwingPoint(
                    price=high,
                    index=i,
                    timestamp=ohlc.index[i],
                    is_high=True,
                ))

            # Check for swing low
            left_lows = ohlc.iloc[i-n:i]["low"].values
            right_lows = ohlc.iloc[i+1:i+n+1]["low"].values

            if low < min(left_lows) and low < min(right_lows):
                self._swings.append(SwingPoint(
                    price=low,
                    index=i,
                    timestamp=ohlc.index[i],
                    is_high=False,
                ))

        # Sort by index
        self._swings.sort(key=lambda s: s.index)

    def _determine_initial_trend(self):
        """Determine initial trend from swing sequence."""
        highs = [s for s in self._swings if s.is_high]
        lows = [s for s in self._swings if not s.is_high]

        if len(highs) < 2 or len(lows) < 2:
            self._current_trend = Trend.NEUTRAL
            return

        recent_highs = sorted(highs, key=lambda s: s.index)[-2:]
        recent_lows = sorted(lows, key=lambda s: s.index)[-2:]

        hh = recent_highs[1].price > recent_highs[0].price
        hl = recent_lows[1].price > recent_lows[0].price
        lh = recent_highs[1].price < recent_highs[0].price
        ll = recent_lows[1].price < recent_lows[0].price

        if hh and hl:
            self._current_trend = Trend.BULLISH
        elif lh and ll:
            self._current_trend = Trend.BEARISH
        else:
            self._current_trend = Trend.NEUTRAL

    def _detect_breaks(self, ohlc: pd.DataFrame, symbol: str, timeframe: str):
        """Detect structure breaks."""

        for i in range(len(ohlc)):
            close = ohlc.iloc[i]["close"]
            atr = self._atr.iloc[i] if self._atr is not None and not pd.isna(self._atr.iloc[i]) else 0.001

            for swing in self._swings:
                if not swing.is_protected or swing.index >= i:
                    continue

                # Check for break of swing high (bullish break)
                if swing.is_high and close > swing.price:
                    has_disp, disp_size = self._check_displacement(ohlc, i, swing.price, True, atr)

                    if not self.require_displacement or has_disp:
                        signal = self._create_break_signal(
                            ohlc, i, swing, True, has_disp, disp_size, symbol, timeframe
                        )
                        self._breaks.append(signal)
                        swing.is_protected = False
                        swing.broken_at = i
                        self._update_trend(signal)

                # Check for break of swing low (bearish break)
                elif not swing.is_high and close < swing.price:
                    has_disp, disp_size = self._check_displacement(ohlc, i, swing.price, False, atr)

                    if not self.require_displacement or has_disp:
                        signal = self._create_break_signal(
                            ohlc, i, swing, False, has_disp, disp_size, symbol, timeframe
                        )
                        self._breaks.append(signal)
                        swing.is_protected = False
                        swing.broken_at = i
                        self._update_trend(signal)

    def _check_displacement(
        self,
        ohlc: pd.DataFrame,
        idx: int,
        level: float,
        bullish: bool,
        atr: float,
    ) -> Tuple[bool, float]:
        """Check for displacement on the break."""
        candle = ohlc.iloc[idx]
        body = abs(candle["close"] - candle["open"])

        is_displacement = body > atr * self.displacement_atr_mult

        if bullish:
            correct_direction = candle["close"] > candle["open"]
            broke_cleanly = candle["close"] > level
        else:
            correct_direction = candle["close"] < candle["open"]
            broke_cleanly = candle["close"] < level

        has_displacement = is_displacement and correct_direction and broke_cleanly

        return has_displacement, body / self.pip_size

    def _create_break_signal(
        self,
        ohlc: pd.DataFrame,
        idx: int,
        swing: SwingPoint,
        bullish_break: bool,
        has_disp: bool,
        disp_size: float,
        symbol: str,
        timeframe: str,
    ) -> StructureBreakSignal:
        """Create a structure break signal."""

        previous_trend = self._current_trend

        # Classify the break
        if previous_trend == Trend.NEUTRAL:
            break_type = BreakType.BOS
            new_direction = Trend.BULLISH if bullish_break else Trend.BEARISH
            is_reversal = False
            is_continuation = True
        elif previous_trend == Trend.BULLISH:
            if bullish_break:
                # Breaking high in uptrend = continuation
                break_type = BreakType.BOS
                new_direction = Trend.BULLISH
                is_reversal = False
                is_continuation = True
            else:
                # Breaking low in uptrend = reversal
                break_type = BreakType.MSS if has_disp else BreakType.CHOCH
                new_direction = Trend.BEARISH
                is_reversal = True
                is_continuation = False
        else:  # BEARISH
            if not bullish_break:
                # Breaking low in downtrend = continuation
                break_type = BreakType.BOS
                new_direction = Trend.BEARISH
                is_reversal = False
                is_continuation = True
            else:
                # Breaking high in downtrend = reversal
                break_type = BreakType.MSS if has_disp else BreakType.CHOCH
                new_direction = Trend.BULLISH
                is_reversal = True
                is_continuation = False

        # Calculate entry zone (the FVG or OB that should form)
        candle = ohlc.iloc[idx]
        if bullish_break:
            entry_top = candle["close"]
            entry_bottom = swing.price
            stop_loss = swing.price - (10 * self.pip_size)
        else:
            entry_top = swing.price
            entry_bottom = candle["close"]
            stop_loss = swing.price + (10 * self.pip_size)

        # Calculate confidence
        confidence = 0.5
        notes = []

        if has_disp:
            confidence += 0.2
            notes.append("Displacement confirmed")

        if is_reversal and break_type == BreakType.MSS:
            confidence += 0.15
            notes.append("MSS - Strong reversal signal")

        if disp_size > 20:
            confidence += 0.1
            notes.append(f"Large displacement: {disp_size:.0f} pips")

        return StructureBreakSignal(
            break_type=break_type,
            direction=new_direction,
            break_time=ohlc.index[idx],
            break_index=idx,
            broken_level=swing.price,
            break_price=candle["close"],
            has_displacement=has_disp,
            displacement_size=disp_size,
            previous_trend=previous_trend,
            is_reversal=is_reversal,
            is_continuation=is_continuation,
            entry_zone_top=entry_top,
            entry_zone_bottom=entry_bottom,
            stop_loss=stop_loss,
            confidence=min(confidence, 1.0),
            timeframe=timeframe,
            symbol=symbol,
            notes=notes,
        )

    def _update_trend(self, signal: StructureBreakSignal):
        """Update current trend after a break."""
        self._current_trend = signal.direction

    def format_signal(self, signal: StructureBreakSignal) -> str:
        """Format a signal for display."""
        direction = "🟢 BULLISH" if signal.direction == Trend.BULLISH else "🔴 BEARISH"
        break_icon = {
            BreakType.BOS: "📈",
            BreakType.MSS: "🔄",
            BreakType.CHOCH: "⚠️",
            BreakType.INTERNAL: "📊",
            BreakType.EXTERNAL: "🎯",
        }

        disp_str = "✅" if signal.has_displacement else "❌"
        rev_str = "Yes" if signal.is_reversal else "No"
        cont_str = "Yes" if signal.is_continuation else "No"
        top_str = f"{signal.entry_zone_top:.5f}" if signal.entry_zone_top else "N/A"
        bottom_str = f"{signal.entry_zone_bottom:.5f}" if signal.entry_zone_bottom else "N/A"
        stop_str = f"{signal.stop_loss:.5f}" if signal.stop_loss else "N/A"
        icon = break_icon.get(signal.break_type, "📊")

        return f"""
{'='*60}
{icon} STRUCTURE BREAK - {signal.symbol} {signal.timeframe}
{'='*60}
Type: {signal.break_type.value.upper()}
Direction: {direction}
Time: {signal.break_time}

📊 Break Details:
   Broken level: {signal.broken_level:.5f}
   Break price: {signal.break_price:.5f}
   Displacement: {disp_str} ({signal.displacement_size:.0f} pips)

📈 Context:
   Previous trend: {signal.previous_trend.value}
   Reversal: {rev_str}
   Continuation: {cont_str}

💰 Entry Zone:
   Top: {top_str}
   Bottom: {bottom_str}
   Stop: {stop_str}

📊 Confidence: {signal.confidence*100:.0f}%
Notes: {', '.join(signal.notes)}
{'='*60}
"""


def analyze_structure(
    ohlc: pd.DataFrame,
    symbol: str = "",
    timeframe: str = "",
    **kwargs
) -> List[StructureBreakSignal]:
    """Quick function to analyze market structure."""
    analyzer = EnhancedStructureAnalyzer(**kwargs)
    return analyzer.analyze(ohlc, symbol, timeframe)

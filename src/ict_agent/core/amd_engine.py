"""AMD Engine - Accumulation, Manipulation, Distribution

ICT's Power of Three / AMD Model:
- Accumulation: Smart money builds position (consolidation)
- Manipulation: False breakout / Judas swing (liquidity grab)
- Distribution: True directional move (expansion)

This engine integrates with:
- Stop Hunt detection (manipulation phase)
- Structure Breaks (distribution phase)
- Time-based analysis (session context)
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Optional, List, Tuple
import pandas as pd
import numpy as np
from zoneinfo import ZoneInfo


class Phase(Enum):
    ACCUMULATION = "accumulation"
    MANIPULATION = "manipulation"
    DISTRIBUTION = "distribution"
    UNKNOWN = "unknown"


class SessionType(Enum):
    ASIAN = "asian"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_PM = "ny_pm"
    OVERLAP = "overlap"
    OFF_SESSION = "off_session"


class Direction(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    UNKNOWN = "unknown"


@dataclass
class AccumulationRange:
    """Detected accumulation range."""
    high: float
    low: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    start_index: int
    end_index: int
    range_pips: float
    is_tight: bool
    candle_count: int


@dataclass
class ManipulationEvent:
    """Detected manipulation (Judas swing / false breakout)."""
    direction: str  # "up" or "down"
    event_time: pd.Timestamp
    event_index: int
    broken_level: float  # Which accumulation level was broken
    extreme_price: float  # How far it went
    reversal_confirmed: bool
    sweep_pips: float


@dataclass
class AMDState:
    """Complete AMD model state."""
    current_phase: Phase
    expected_direction: Direction

    # Accumulation
    accumulation: Optional[AccumulationRange] = None

    # Manipulation
    manipulation: Optional[ManipulationEvent] = None
    manipulation_level: Optional[float] = None

    # Distribution
    distribution_active: bool = False
    distribution_start: Optional[pd.Timestamp] = None

    # Session context
    session: SessionType = SessionType.OFF_SESSION

    # Trade info
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    risk_reward: Optional[float] = None

    # Confidence
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)


class AMDEngine:
    """
    Detects and tracks AMD (Accumulation-Manipulation-Distribution) cycle.

    ICT Power of Three:
    1. Accumulation (first 1/3 of session) - Range/consolidation
    2. Manipulation (middle) - False breakout to grab liquidity
    3. Distribution (final 2/3) - True move in opposite direction

    Session Application:
    - Asian = Often accumulation for London
    - London open = Manipulation (Judas)
    - London/NY = Distribution

    Intraday Application:
    - First 30 min of session = Accumulation
    - Next 30 min = Manipulation
    - Rest = Distribution
    """

    # Kill zones in NY time
    SESSIONS = {
        SessionType.ASIAN: (time(19, 0), time(0, 0)),      # 7 PM - 12 AM
        SessionType.LONDON: (time(2, 0), time(5, 0)),      # 2 AM - 5 AM
        SessionType.NY_AM: (time(7, 0), time(10, 0)),      # 7 AM - 10 AM
        SessionType.NY_PM: (time(13, 30), time(16, 0)),    # 1:30 PM - 4 PM
    }

    def __init__(
        self,
        accumulation_max_pips: float = 30.0,
        min_manipulation_pips: float = 5.0,
        pip_size: float = 0.0001,
        timezone: str = "America/New_York",
    ):
        self.accumulation_max_pips = accumulation_max_pips
        self.min_manipulation_pips = min_manipulation_pips
        self.pip_size = pip_size
        self.tz = ZoneInfo(timezone)

        self._current_state: Optional[AMDState] = None
        self._atr: Optional[pd.Series] = None

    def analyze(
        self,
        ohlc: pd.DataFrame,
        symbol: str = "",
        timeframe: str = "",
    ) -> AMDState:
        """
        Analyze price data for AMD cycle.

        Returns current AMD state with phase detection.
        """
        if len(ohlc) < 20:
            return AMDState(Phase.UNKNOWN, Direction.UNKNOWN)

        self._calculate_atr(ohlc)

        # Determine current session
        session = self._get_current_session(ohlc)

        # Get session data
        session_data = self._get_session_data(ohlc)

        if len(session_data) < 5:
            return AMDState(Phase.UNKNOWN, Direction.UNKNOWN, session=session)

        # Detect accumulation
        accumulation = self._detect_accumulation(session_data)

        # Detect manipulation
        manipulation = None
        if accumulation:
            manipulation = self._detect_manipulation(session_data, accumulation)

        # Determine current phase and direction
        state = self._build_state(session_data, session, accumulation, manipulation)

        # Calculate trade levels if in distribution
        if state.current_phase == Phase.DISTRIBUTION and state.manipulation:
            self._calculate_trade_levels(state)

        self._current_state = state
        return state

    def get_current_state(self) -> Optional[AMDState]:
        """Get current AMD state."""
        return self._current_state

    def _calculate_atr(self, ohlc: pd.DataFrame, period: int = 14):
        high, low = ohlc["high"], ohlc["low"]
        close = ohlc["close"].shift(1)
        tr = pd.concat([high - low, abs(high - close), abs(low - close)], axis=1).max(axis=1)
        self._atr = tr.rolling(window=period).mean()

    def _get_current_session(self, ohlc: pd.DataFrame) -> SessionType:
        """Determine current trading session."""
        if ohlc.index.tz is None:
            current_time = ohlc.index[-1].tz_localize("UTC").tz_convert(self.tz)
        else:
            current_time = ohlc.index[-1].tz_convert(self.tz)

        current_hour = current_time.time()

        for session, (start, end) in self.SESSIONS.items():
            if start <= end:
                if start <= current_hour <= end:
                    return session
            else:  # Crosses midnight
                if current_hour >= start or current_hour <= end:
                    return session

        return SessionType.OFF_SESSION

    def _get_session_data(self, ohlc: pd.DataFrame, lookback_hours: int = 4) -> pd.DataFrame:
        """Get data for current session context."""
        # Use last N hours of data
        if len(ohlc) < 10:
            return ohlc

        # For simplicity, use last ~50 candles (adjustable based on timeframe)
        return ohlc.tail(50)

    def _detect_accumulation(self, data: pd.DataFrame) -> Optional[AccumulationRange]:
        """Detect accumulation range (consolidation)."""

        # Look at first portion of session data for accumulation
        accum_candles = min(len(data) // 3, 12)  # First third or max 12 candles

        if accum_candles < 3:
            return None

        accum_data = data.head(accum_candles)

        high = accum_data["high"].max()
        low = accum_data["low"].min()
        range_pips = (high - low) / self.pip_size

        # Check if range is tight enough
        is_tight = range_pips <= self.accumulation_max_pips

        return AccumulationRange(
            high=high,
            low=low,
            start_time=accum_data.index[0],
            end_time=accum_data.index[-1],
            start_index=0,
            end_index=accum_candles - 1,
            range_pips=range_pips,
            is_tight=is_tight,
            candle_count=accum_candles,
        )

    def _detect_manipulation(
        self,
        data: pd.DataFrame,
        accum: AccumulationRange,
    ) -> Optional[ManipulationEvent]:
        """Detect manipulation (false breakout / Judas swing)."""

        # Look at middle portion for manipulation
        manip_start = accum.end_index + 1
        manip_end = min(manip_start + 12, len(data))

        if manip_start >= len(data):
            return None

        manip_data = data.iloc[manip_start:manip_end]

        if len(manip_data) < 2:
            return None

        # Check for breakout above accumulation high then rejection
        for i in range(len(manip_data)):
            candle = manip_data.iloc[i]

            # Breakout above (Judas UP - bearish setup)
            if candle["high"] > accum.high:
                sweep_pips = (candle["high"] - accum.high) / self.pip_size

                if sweep_pips >= self.min_manipulation_pips:
                    # Check for rejection (close back in range)
                    if candle["close"] <= accum.high:
                        return ManipulationEvent(
                            direction="up",
                            event_time=manip_data.index[i],
                            event_index=manip_start + i,
                            broken_level=accum.high,
                            extreme_price=candle["high"],
                            reversal_confirmed=candle["close"] < candle["open"],
                            sweep_pips=sweep_pips,
                        )

            # Breakout below (Judas DOWN - bullish setup)
            if candle["low"] < accum.low:
                sweep_pips = (accum.low - candle["low"]) / self.pip_size

                if sweep_pips >= self.min_manipulation_pips:
                    if candle["close"] >= accum.low:
                        return ManipulationEvent(
                            direction="down",
                            event_time=manip_data.index[i],
                            event_index=manip_start + i,
                            broken_level=accum.low,
                            extreme_price=candle["low"],
                            reversal_confirmed=candle["close"] > candle["open"],
                            sweep_pips=sweep_pips,
                        )

        return None

    def _build_state(
        self,
        data: pd.DataFrame,
        session: SessionType,
        accum: Optional[AccumulationRange],
        manip: Optional[ManipulationEvent],
    ) -> AMDState:
        """Build AMD state from detected components."""

        notes = []
        confidence = 0.3  # Base confidence

        # No accumulation = unknown phase
        if not accum:
            return AMDState(
                current_phase=Phase.UNKNOWN,
                expected_direction=Direction.UNKNOWN,
                session=session,
            )

        # Accumulation detected
        if accum.is_tight:
            confidence += 0.1
            notes.append(f"Tight accumulation: {accum.range_pips:.0f} pips")
        else:
            notes.append(f"Wide accumulation: {accum.range_pips:.0f} pips")

        # No manipulation yet = still in accumulation or early manipulation
        if not manip:
            current_price = data.iloc[-1]["close"]

            # Check if we're breaking out (manipulation starting)
            if current_price > accum.high or current_price < accum.low:
                return AMDState(
                    current_phase=Phase.MANIPULATION,
                    expected_direction=Direction.UNKNOWN,
                    accumulation=accum,
                    session=session,
                    confidence=confidence,
                    notes=notes,
                )
            else:
                return AMDState(
                    current_phase=Phase.ACCUMULATION,
                    expected_direction=Direction.UNKNOWN,
                    accumulation=accum,
                    session=session,
                    confidence=confidence,
                    notes=notes,
                )

        # Manipulation detected - determine expected direction
        if manip.direction == "up":
            # Swept highs = expect bearish distribution
            expected = Direction.BEARISH
            notes.append(f"Judas UP sweep {manip.sweep_pips:.0f} pips - expect BEARISH")
        else:
            # Swept lows = expect bullish distribution
            expected = Direction.BULLISH
            notes.append(f"Judas DOWN sweep {manip.sweep_pips:.0f} pips - expect BULLISH")

        if manip.reversal_confirmed:
            confidence += 0.2
            notes.append("Reversal candle confirmed")

        # Check if we're now in distribution
        current_price = data.iloc[-1]["close"]

        if manip.direction == "up" and current_price < accum.low:
            # Broke down = distribution bearish
            phase = Phase.DISTRIBUTION
            confidence += 0.2
            notes.append("Distribution active - broke below accumulation")
        elif manip.direction == "down" and current_price > accum.high:
            # Broke up = distribution bullish
            phase = Phase.DISTRIBUTION
            confidence += 0.2
            notes.append("Distribution active - broke above accumulation")
        else:
            phase = Phase.MANIPULATION

        return AMDState(
            current_phase=phase,
            expected_direction=expected,
            accumulation=accum,
            manipulation=manip,
            manipulation_level=manip.extreme_price,
            distribution_active=(phase == Phase.DISTRIBUTION),
            distribution_start=data.index[-1] if phase == Phase.DISTRIBUTION else None,
            session=session,
            confidence=min(confidence, 1.0),
            notes=notes,
        )

    def _calculate_trade_levels(self, state: AMDState):
        """Calculate entry, stop, and target for distribution trade."""

        if not state.manipulation or not state.accumulation:
            return

        accum = state.accumulation
        manip = state.manipulation

        if state.expected_direction == Direction.BEARISH:
            # Sell setup
            state.entry_price = accum.high  # Enter at top of accumulation
            state.stop_loss = manip.extreme_price + (5 * self.pip_size)
            # Target: accumulation range projected down
            state.target_price = accum.low - (accum.high - accum.low)
        else:
            # Buy setup
            state.entry_price = accum.low
            state.stop_loss = manip.extreme_price - (5 * self.pip_size)
            state.target_price = accum.high + (accum.high - accum.low)

        if state.entry_price and state.stop_loss and state.target_price:
            risk = abs(state.entry_price - state.stop_loss)
            reward = abs(state.target_price - state.entry_price)
            state.risk_reward = reward / risk if risk > 0 else 0

    def format_state(self, state: AMDState) -> str:
        """Format AMD state for display."""
        phase_icon = {
            Phase.ACCUMULATION: "📦",
            Phase.MANIPULATION: "🎭",
            Phase.DISTRIBUTION: "🚀",
            Phase.UNKNOWN: "❓",
        }

        direction_icon = {
            Direction.BULLISH: "🟢 BULLISH",
            Direction.BEARISH: "🔴 BEARISH",
            Direction.UNKNOWN: "⚪ UNKNOWN",
        }

        lines = [
            f"\n{'='*60}",
            f"{phase_icon.get(state.current_phase, '❓')} AMD ANALYSIS",
            f"{'='*60}",
            f"Phase: {state.current_phase.value.upper()}",
            f"Direction: {direction_icon.get(state.expected_direction, 'Unknown')}",
            f"Session: {state.session.value}",
            f"Confidence: {state.confidence*100:.0f}%",
        ]

        if state.accumulation:
            lines.extend([
                f"",
                f"📦 Accumulation:",
                f"   Range: {state.accumulation.low:.5f} - {state.accumulation.high:.5f}",
                f"   Size: {state.accumulation.range_pips:.0f} pips ({'✅ Tight' if state.accumulation.is_tight else '⚠️ Wide'})",
            ])

        if state.manipulation:
            lines.extend([
                f"",
                f"🎭 Manipulation:",
                f"   Direction: Judas {state.manipulation.direction.upper()}",
                f"   Sweep: {state.manipulation.sweep_pips:.0f} pips",
                f"   Extreme: {state.manipulation.extreme_price:.5f}",
                f"   Reversal: {'✅' if state.manipulation.reversal_confirmed else '❌'}",
            ])

        if state.distribution_active:
            lines.extend([
                f"",
                f"🚀 Distribution:",
                f"   Active: Yes",
                f"   Entry: {state.entry_price:.5f if state.entry_price else 'N/A'}",
                f"   Stop: {state.stop_loss:.5f if state.stop_loss else 'N/A'}",
                f"   Target: {state.target_price:.5f if state.target_price else 'N/A'}",
                f"   R:R: {state.risk_reward:.1f if state.risk_reward else 'N/A'}",
            ])

        if state.notes:
            lines.extend([f"", f"📝 Notes:"])
            for note in state.notes:
                lines.append(f"   • {note}")

        lines.append("="*60)

        return "\n".join(lines)


def analyze_amd(
    ohlc: pd.DataFrame,
    symbol: str = "",
    timeframe: str = "",
    **kwargs
) -> AMDState:
    """Quick function to analyze AMD cycle."""
    engine = AMDEngine(**kwargs)
    return engine.analyze(ohlc, symbol, timeframe)

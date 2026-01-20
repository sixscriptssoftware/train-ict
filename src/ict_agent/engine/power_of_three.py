#!/usr/bin/env python3
"""
ICT Power of Three (PO3) Session Analyzer

Tracks the daily AMD (Accumulation → Manipulation → Distribution) cycle:
1. ACCUMULATION: Asian session builds the range
2. MANIPULATION: London/early NY sweeps one side (Judas swing)
3. DISTRIBUTION: Real move in opposite direction

ICT teaches: "The high or low of the day is formed during the first
few hours of trading" - knowing which one helps you trade the distribution.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

NY_TZ = ZoneInfo("America/New_York")


class PO3Phase(Enum):
    ACCUMULATION = "accumulation"
    MANIPULATION = "manipulation"
    DISTRIBUTION = "distribution"
    UNKNOWN = "unknown"


class DailyBias(Enum):
    BULLISH = "bullish"  # Low of day likely in, expecting higher
    BEARISH = "bearish"  # High of day likely in, expecting lower
    NEUTRAL = "neutral"  # Not yet determined


@dataclass
class PO3Analysis:
    """Power of Three analysis result."""
    phase: PO3Phase
    bias: DailyBias

    # Session ranges
    asian_high: float
    asian_low: float
    asian_range_pips: float

    # Manipulation detection
    manipulation_detected: bool
    manipulation_direction: str  # "swept_lows" or "swept_highs"
    manipulation_price: float

    # Current state
    current_price: float
    session_high: float
    session_low: float

    # Projections
    distribution_target: float
    confidence: float

    timestamp: datetime
    description: str


class PowerOfThreeAnalyzer:
    """
    Analyzes the daily Power of Three cycle.

    Key times (NY):
    - Asian: 7 PM - 12 AM (accumulation)
    - London: 2 AM - 5 AM (early manipulation)
    - NY AM: 7 AM - 10 AM (manipulation/distribution)
    - NY PM: 1 PM - 4 PM (continuation/reversal)
    """

    def __init__(self):
        self.asian_start = time(19, 0)  # 7 PM NY (previous day)
        self.asian_end = time(0, 0)     # 12 AM NY
        self.london_start = time(2, 0)
        self.london_end = time(5, 0)
        self.ny_am_start = time(7, 0)
        self.ny_am_end = time(10, 0)

    def get_session_data(
        self,
        df: pd.DataFrame,
        start_time: time,
        end_time: time,
        date: datetime = None
    ) -> pd.DataFrame:
        """Extract data for a specific session."""
        if date is None:
            date = datetime.now(NY_TZ).date()

        # Handle overnight sessions (Asian)
        if start_time > end_time:
            # Previous day start to midnight
            prev_date = date - timedelta(days=1)
            start_dt = datetime.combine(prev_date, start_time, tzinfo=NY_TZ)
            end_dt = datetime.combine(date, end_time, tzinfo=NY_TZ)
        else:
            start_dt = datetime.combine(date, start_time, tzinfo=NY_TZ)
            end_dt = datetime.combine(date, end_time, tzinfo=NY_TZ)

        # Filter dataframe
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(NY_TZ)
        else:
            df.index = df.index.tz_convert(NY_TZ)

        mask = (df.index >= start_dt) & (df.index < end_dt)
        return df[mask]

    def detect_manipulation(
        self,
        current_high: float,
        current_low: float,
        asian_high: float,
        asian_low: float,
        current_price: float
    ) -> Tuple[bool, str, float]:
        """
        Detect if manipulation (Judas swing) has occurred.

        Manipulation = price sweeps Asian range then reverses.
        """
        buffer = 0.0002  # 2 pip buffer

        # Swept Asian lows then came back up = bullish manipulation
        if current_low < asian_low - buffer and current_price > asian_low:
            return True, "swept_lows", current_low

        # Swept Asian highs then came back down = bearish manipulation
        if current_high > asian_high + buffer and current_price < asian_high:
            return True, "swept_highs", current_high

        return False, "", 0.0

    def determine_bias(
        self,
        manipulation_detected: bool,
        manipulation_direction: str,
        current_price: float,
        asian_mid: float
    ) -> DailyBias:
        """
        Determine daily bias based on manipulation.

        ICT rule: The manipulation tells you the real direction.
        - Sweep lows first → BULLISH day (low of day in)
        - Sweep highs first → BEARISH day (high of day in)
        """
        if manipulation_detected:
            if manipulation_direction == "swept_lows":
                return DailyBias.BULLISH
            elif manipulation_direction == "swept_highs":
                return DailyBias.BEARISH

        # No clear manipulation yet - use price location
        if current_price > asian_mid:
            return DailyBias.BULLISH  # Tentative
        else:
            return DailyBias.BEARISH  # Tentative

    def get_current_phase(self) -> PO3Phase:
        """Determine current PO3 phase based on time."""
        now = datetime.now(NY_TZ).time()

        # Asian session (accumulation)
        if now >= self.asian_start or now < self.asian_end:
            return PO3Phase.ACCUMULATION

        # London (early manipulation)
        if self.london_start <= now < self.london_end:
            return PO3Phase.MANIPULATION

        # NY AM (manipulation/distribution)
        if self.ny_am_start <= now < self.ny_am_end:
            return PO3Phase.MANIPULATION  # Could be either

        # After NY AM (distribution)
        if now >= self.ny_am_end:
            return PO3Phase.DISTRIBUTION

        return PO3Phase.UNKNOWN

    def calculate_target(
        self,
        bias: DailyBias,
        asian_high: float,
        asian_low: float,
        manipulation_price: float
    ) -> float:
        """Calculate distribution target based on bias."""
        asian_range = asian_high - asian_low

        if bias == DailyBias.BULLISH:
            # Target is Asian high + range (or more)
            return asian_high + (asian_range * 1.5)
        elif bias == DailyBias.BEARISH:
            # Target is Asian low - range (or more)
            return asian_low - (asian_range * 1.5)

        return (asian_high + asian_low) / 2  # Neutral = midpoint

    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "EUR_USD"
    ) -> PO3Analysis:
        """
        Perform full Power of Three analysis.

        Args:
            df: OHLC data (should include Asian session + current session)
            symbol: Currency pair

        Returns:
            PO3Analysis with current phase, bias, and targets
        """
        now = datetime.now(NY_TZ)

        # Get Asian session data
        asian_data = self.get_session_data(df, self.asian_start, self.asian_end)

        if asian_data.empty:
            # Fallback: use last 20 candles as "range"
            asian_data = df.tail(20)

        asian_high = asian_data['high'].max()
        asian_low = asian_data['low'].min()
        asian_range = (asian_high - asian_low) * 10000  # pips
        asian_mid = (asian_high + asian_low) / 2

        # Current session data (everything after Asian)
        current_price = df['close'].iloc[-1]
        session_high = df['high'].iloc[-20:].max()  # Last 20 candles
        session_low = df['low'].iloc[-20:].min()

        # Detect manipulation
        manip_detected, manip_direction, manip_price = self.detect_manipulation(
            session_high, session_low, asian_high, asian_low, current_price
        )

        # Determine bias
        bias = self.determine_bias(manip_detected, manip_direction, current_price, asian_mid)

        # Current phase
        phase = self.get_current_phase()

        # Calculate target
        target = self.calculate_target(bias, asian_high, asian_low, manip_price)

        # Confidence
        confidence = 0.5
        if manip_detected:
            confidence = 0.75
            if phase == PO3Phase.DISTRIBUTION:
                confidence = 0.85

        # Build description
        desc = f"PO3 {phase.value.upper()}: "
        if manip_detected:
            if manip_direction == "swept_lows":
                desc += f"Swept Asian lows at {manip_price:.5f} → BULLISH. "
            else:
                desc += f"Swept Asian highs at {manip_price:.5f} → BEARISH. "
            desc += f"Target: {target:.5f}"
        else:
            desc += f"No clear manipulation yet. Asian range: {asian_range:.1f} pips."

        return PO3Analysis(
            phase=phase,
            bias=bias,
            asian_high=asian_high,
            asian_low=asian_low,
            asian_range_pips=asian_range,
            manipulation_detected=manip_detected,
            manipulation_direction=manip_direction,
            manipulation_price=manip_price,
            current_price=current_price,
            session_high=session_high,
            session_low=session_low,
            distribution_target=target,
            confidence=confidence,
            timestamp=now,
            description=desc
        )

    def format_analysis(self, analysis: PO3Analysis) -> str:
        """Format PO3 analysis for display."""
        phase_emoji = {
            PO3Phase.ACCUMULATION: "📦",
            PO3Phase.MANIPULATION: "🎭",
            PO3Phase.DISTRIBUTION: "🚀",
            PO3Phase.UNKNOWN: "❓"
        }

        bias_emoji = {
            DailyBias.BULLISH: "🟢 BULLISH",
            DailyBias.BEARISH: "🔴 BEARISH",
            DailyBias.NEUTRAL: "⚪ NEUTRAL"
        }

        return f"""
╔══════════════════════════════════════════════════════════════╗
║              ⚡ POWER OF THREE ANALYSIS                       ║
╚══════════════════════════════════════════════════════════════╝

{phase_emoji.get(analysis.phase, "?")} Current Phase: {analysis.phase.value.upper()}
{bias_emoji.get(analysis.bias, "?")}  Daily Bias: {analysis.bias.value.upper()}
📊 Confidence: {analysis.confidence * 100:.0f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASIAN SESSION (Accumulation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  High: {analysis.asian_high:.5f}
  Low:  {analysis.asian_low:.5f}
  Range: {analysis.asian_range_pips:.1f} pips

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANIPULATION (Judas Swing)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Detected: {"✅ YES" if analysis.manipulation_detected else "❌ NOT YET"}
  Direction: {analysis.manipulation_direction or "N/A"}
  Price: {analysis.manipulation_price if analysis.manipulation_price else 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT STATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Price: {analysis.current_price:.5f}
  Session High: {analysis.session_high:.5f}
  Session Low: {analysis.session_low:.5f}
  
🎯 DISTRIBUTION TARGET: {analysis.distribution_target:.5f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 {analysis.description}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def analyze_po3(symbol: str = "EUR_USD", timeframe: str = "15m") -> PO3Analysis:
    """Quick function to run PO3 analysis."""
    from ict_agent.data.oanda_fetcher import get_oanda_data

    df = get_oanda_data(symbol, timeframe=timeframe, count=200)
    if df.empty:
        return None

    analyzer = PowerOfThreeAnalyzer()
    return analyzer.analyze(df, symbol)


if __name__ == "__main__":
    from ict_agent.data.oanda_fetcher import get_oanda_data

    print("⚡ Running Power of Three Analysis...")

    for symbol in ["EUR_USD", "GBP_USD"]:
        df = get_oanda_data(symbol, timeframe="15m", count=200)
        if df.empty:
            print(f"❌ Could not get data for {symbol}")
            continue

        analyzer = PowerOfThreeAnalyzer()
        analysis = analyzer.analyze(df, symbol)
        print(f"\n{'='*60}")
        print(f"  {symbol}")
        print(f"{'='*60}")
        print(analyzer.format_analysis(analysis))

"""Stop Hunt / Liquidity Sweep Detection

Enhanced detection for stop hunts with:
- Institutional volume confirmation
- Rejection quality scoring
- Trade level calculation
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import pandas as pd
import numpy as np


class HuntType(Enum):
    BUY_SIDE_SWEEP = "buy_side_sweep"
    SELL_SIDE_SWEEP = "sell_side_sweep"
    JUDAS_UP = "judas_up"
    JUDAS_DOWN = "judas_down"
    EQUAL_HIGH_SWEEP = "equal_high_sweep"
    EQUAL_LOW_SWEEP = "equal_low_sweep"


class RejectionQuality(Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VIOLENT = "violent"


@dataclass
class LiquidityTarget:
    price: float
    level_type: str
    strength: int
    index: int
    timestamp: pd.Timestamp
    is_protected: bool = True


@dataclass
class StopHunt:
    hunt_type: HuntType
    sweep_time: pd.Timestamp
    sweep_index: int
    target_level: float
    sweep_extreme: float
    close_price: float
    wick_size_pips: float
    body_rejection_pips: float
    rejection_quality: RejectionQuality
    volume_spike: bool
    volume_ratio: float
    displacement_confirmed: bool
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    risk_reward: Optional[float] = None
    timeframe: str = ""
    symbol: str = ""
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)


class StopHuntDetector:
    """
    Detects stop hunts and liquidity sweeps with ICT principles.

    ICT Principles:
    - Smart money uses retail stop losses for liquidity
    - Valid hunts show REJECTION (wick with body close away from extreme)
    - Equal highs/lows are stronger liquidity targets
    """

    def __init__(
        self,
        swing_lookback: int = 10,
        equal_level_tolerance: float = 0.0003,
        min_wick_pips: float = 3.0,
        pip_size: float = 0.0001,
        volume_spike_mult: float = 1.5,
    ):
        self.swing_lookback = swing_lookback
        self.equal_level_tolerance = equal_level_tolerance
        self.min_wick_pips = min_wick_pips
        self.pip_size = pip_size
        self.volume_spike_mult = volume_spike_mult
        self._liquidity_targets: List[LiquidityTarget] = []
        self._detected_hunts: List[StopHunt] = []
        self._atr: Optional[pd.Series] = None

    def detect(
        self,
        ohlc: pd.DataFrame,
        symbol: str = "",
        timeframe: str = ""
    ) -> List[StopHunt]:
        """Detect stop hunts in price data."""
        if len(ohlc) < self.swing_lookback * 2 + 5:
            return []

        self._detected_hunts = []
        self._calculate_atr(ohlc)
        self._map_liquidity(ohlc)
        self._scan_for_sweeps(ohlc, symbol, timeframe)
        self._validate_hunts()

        return self._detected_hunts

    def get_active_targets(self, side: Optional[str] = None) -> List[LiquidityTarget]:
        """Get liquidity targets not yet swept."""
        targets = [t for t in self._liquidity_targets if t.is_protected]
        if side == "buy":
            return [t for t in targets if "high" in t.level_type]
        elif side == "sell":
            return [t for t in targets if "low" in t.level_type]
        return targets

    def _calculate_atr(self, ohlc: pd.DataFrame, period: int = 14):
        high, low = ohlc["high"], ohlc["low"]
        close = ohlc["close"].shift(1)
        tr = pd.concat([high - low, abs(high - close), abs(low - close)], axis=1).max(axis=1)
        self._atr = tr.rolling(window=period).mean()

    def _map_liquidity(self, ohlc: pd.DataFrame):
        """Map all liquidity targets."""
        self._liquidity_targets = []
        n = self.swing_lookback
        swing_highs, swing_lows = [], []

        for i in range(n, len(ohlc) - n):
            high, low = ohlc.iloc[i]["high"], ohlc.iloc[i]["low"]
            left_h = ohlc.iloc[i-n:i]["high"].values
            right_h = ohlc.iloc[i+1:i+n+1]["high"].values

            if high > max(left_h) and high > max(right_h):
                t = LiquidityTarget(high, "swing_high", 1, i, ohlc.index[i])
                swing_highs.append(t)
                self._liquidity_targets.append(t)

            left_l = ohlc.iloc[i-n:i]["low"].values
            right_l = ohlc.iloc[i+1:i+n+1]["low"].values

            if low < min(left_l) and low < min(right_l):
                t = LiquidityTarget(low, "swing_low", 1, i, ohlc.index[i])
                swing_lows.append(t)
                self._liquidity_targets.append(t)

        # Detect equal levels (stronger liquidity)
        for swing in swing_highs:
            matches = [s for s in swing_highs
                      if s != swing and abs(s.price - swing.price) <= self.equal_level_tolerance]
            if matches:
                swing.level_type = "equal_high"
                swing.strength = len(matches) + 1

        for swing in swing_lows:
            matches = [s for s in swing_lows
                      if s != swing and abs(s.price - swing.price) <= self.equal_level_tolerance]
            if matches:
                swing.level_type = "equal_low"
                swing.strength = len(matches) + 1

    def _scan_for_sweeps(self, ohlc: pd.DataFrame, symbol: str, timeframe: str):
        """Scan for liquidity sweeps with rejection."""
        avg_vol = ohlc["volume"].rolling(20).mean() if "volume" in ohlc.columns else None

        for target in self._liquidity_targets:
            if not target.is_protected:
                continue

            for i in range(target.index + 1, len(ohlc)):
                candle = ohlc.iloc[i]
                high, low, close = candle["high"], candle["low"], candle["close"]

                # Buy-side sweep (swept highs, expect reversal down)
                if "high" in target.level_type and high > target.price and close < target.price:
                    hunt = self._create_hunt(ohlc, i, target, True, symbol, timeframe, avg_vol)
                    if hunt:
                        target.is_protected = False
                        self._detected_hunts.append(hunt)
                    break

                # Sell-side sweep (swept lows, expect reversal up)
                if "low" in target.level_type and low < target.price and close > target.price:
                    hunt = self._create_hunt(ohlc, i, target, False, symbol, timeframe, avg_vol)
                    if hunt:
                        target.is_protected = False
                        self._detected_hunts.append(hunt)
                    break

    def _create_hunt(self, ohlc, idx, target, is_buy_side, symbol, timeframe, avg_vol):
        """Create a StopHunt from detected sweep."""
        candle = ohlc.iloc[idx]
        high, low, close = candle["high"], candle["low"], candle["close"]

        if is_buy_side:
            wick = (high - target.price) / self.pip_size
            rejection = (high - close) / self.pip_size
            extreme = high
            hunt_type = HuntType.EQUAL_HIGH_SWEEP if "equal" in target.level_type else HuntType.BUY_SIDE_SWEEP
        else:
            wick = (target.price - low) / self.pip_size
            rejection = (close - low) / self.pip_size
            extreme = low
            hunt_type = HuntType.EQUAL_LOW_SWEEP if "equal" in target.level_type else HuntType.SELL_SIDE_SWEEP

        if wick < self.min_wick_pips:
            return None

        # Assess rejection quality
        atr = self._atr.iloc[idx] if self._atr is not None else 0.001
        body = abs(candle["close"] - candle["open"])
        is_correct = (candle["close"] < candle["open"]) if is_buy_side else (candle["close"] > candle["open"])
        range_size = candle["high"] - candle["low"]

        if body > atr * 1.5 and is_correct:
            quality = RejectionQuality.VIOLENT
        elif rejection * self.pip_size > range_size * 0.5 and is_correct:
            quality = RejectionQuality.STRONG
        elif rejection * self.pip_size > range_size * 0.3:
            quality = RejectionQuality.MODERATE
        else:
            quality = RejectionQuality.WEAK

        # Volume analysis
        vol_spike, vol_ratio = False, 1.0
        if avg_vol is not None and "volume" in ohlc.columns:
            avg = avg_vol.iloc[idx]
            if not pd.isna(avg) and avg > 0:
                vol_ratio = candle["volume"] / avg
                vol_spike = vol_ratio > self.volume_spike_mult

        # Displacement check
        disp = self._check_displacement(ohlc, idx, is_buy_side)

        hunt = StopHunt(
            hunt_type=hunt_type,
            sweep_time=ohlc.index[idx],
            sweep_index=idx,
            target_level=target.price,
            sweep_extreme=extreme,
            close_price=close,
            wick_size_pips=wick,
            body_rejection_pips=rejection,
            rejection_quality=quality,
            volume_spike=vol_spike,
            volume_ratio=vol_ratio,
            displacement_confirmed=disp,
            timeframe=timeframe,
            symbol=symbol
        )

        # Calculate trade levels
        self._set_trade_levels(hunt, is_buy_side)

        return hunt

    def _set_trade_levels(self, hunt: StopHunt, is_buy_side: bool):
        """Set entry, stop, and target for the hunt."""
        atr_val = 0.001
        if self._atr is not None and hunt.sweep_index < len(self._atr):
            atr_val = self._atr.iloc[hunt.sweep_index]
            if pd.isna(atr_val):
                atr_val = 0.001

        if is_buy_side:
            hunt.entry_price = hunt.target_level
            hunt.stop_loss = hunt.sweep_extreme + 5 * self.pip_size
            hunt.target_price = hunt.target_level - atr_val * 3
        else:
            hunt.entry_price = hunt.target_level
            hunt.stop_loss = hunt.sweep_extreme - 5 * self.pip_size
            hunt.target_price = hunt.target_level + atr_val * 3

        if hunt.entry_price and hunt.stop_loss and hunt.target_price:
            risk = abs(hunt.entry_price - hunt.stop_loss)
            reward = abs(hunt.target_price - hunt.entry_price)
            hunt.risk_reward = reward / risk if risk > 0 else 0

    def _check_displacement(self, ohlc, idx, is_buy_side, lookforward=3):
        """Check if subsequent candles show displacement."""
        if idx + lookforward >= len(ohlc):
            return False

        atr = self._atr.iloc[idx] if self._atr is not None else 0.001
        if pd.isna(atr):
            atr = 0.001

        for i in range(1, lookforward + 1):
            c = ohlc.iloc[idx + i]
            body = abs(c["close"] - c["open"])
            if is_buy_side and c["close"] < c["open"] and body > atr * 1.5:
                return True
            if not is_buy_side and c["close"] > c["open"] and body > atr * 1.5:
                return True
        return False

    def _validate_hunts(self):
        """Validate and score detected hunts."""
        for hunt in self._detected_hunts:
            score = 0.0
            notes = []

            # Rejection quality
            if hunt.rejection_quality == RejectionQuality.VIOLENT:
                score += 0.30
                notes.append("Violent rejection - strong signal")
            elif hunt.rejection_quality == RejectionQuality.STRONG:
                score += 0.25
                notes.append("Strong rejection")
            elif hunt.rejection_quality == RejectionQuality.MODERATE:
                score += 0.15
            else:
                score += 0.05

            # Equal levels stronger
            if "equal" in hunt.hunt_type.value:
                score += 0.15
                notes.append("Equal level - high probability")

            # Volume confirmation
            if hunt.volume_spike:
                score += 0.15
                notes.append(f"Volume spike {hunt.volume_ratio:.1f}x")

            # Displacement
            if hunt.displacement_confirmed:
                score += 0.20
                notes.append("Displacement confirmed")

            # R:R
            if hunt.risk_reward and hunt.risk_reward >= 2.0:
                score += 0.10
                notes.append(f"R:R {hunt.risk_reward:.1f}")

            hunt.confidence = min(score, 1.0)
            hunt.notes = notes

    def format_hunt(self, hunt: StopHunt) -> str:
        """Format a hunt for display."""
        direction = "🔴 SELL" if "buy" in hunt.hunt_type.value else "🟢 BUY"

        entry_str = f"{hunt.entry_price:.5f}" if hunt.entry_price else "N/A"
        stop_str = f"{hunt.stop_loss:.5f}" if hunt.stop_loss else "N/A"
        target_str = f"{hunt.target_price:.5f}" if hunt.target_price else "N/A"
        rr_str = f"{hunt.risk_reward:.1f}" if hunt.risk_reward else "N/A"
        disp_str = "✅" if hunt.displacement_confirmed else "❌"

        return f"""
{'='*60}
🎯 STOP HUNT DETECTED - {hunt.symbol} {hunt.timeframe}
{'='*60}
Type: {hunt.hunt_type.value}
Time: {hunt.sweep_time}
Direction: {direction}

📊 Levels:
   Target swept: {hunt.target_level:.5f}
   Sweep extreme: {hunt.sweep_extreme:.5f}
   Close: {hunt.close_price:.5f}

📈 Metrics:
   Wick: {hunt.wick_size_pips:.1f} pips
   Rejection: {hunt.rejection_quality.value}
   Volume: {hunt.volume_ratio:.1f}x
   Displacement: {disp_str}

💰 Trade:
   Entry: {entry_str}
   Stop: {stop_str}
   Target: {target_str}
   R:R: {rr_str}

📊 Confidence: {hunt.confidence*100:.0f}%
Notes: {', '.join(hunt.notes)}
{'='*60}
"""


def detect_stop_hunts(
    ohlc: pd.DataFrame,
    symbol: str = "",
    timeframe: str = ""
) -> List[StopHunt]:
    """Quick function to detect stop hunts."""
    return StopHuntDetector().detect(ohlc, symbol, timeframe)

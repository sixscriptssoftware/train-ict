"""Judas Swing Model

ICT's reversal model based on false breakouts and liquidity sweeps.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd

from ict_agent.detectors.liquidity import LiquidityDetector, LiquidityType, LiquiditySweep
from ict_agent.detectors.displacement import DisplacementDetector, DisplacementDirection
from ict_agent.detectors.fvg import FVGDetector, FVGDirection
from ict_agent.detectors.market_structure import MarketStructureAnalyzer, StructureType


@dataclass
class JudasSwingSetup:
    """A valid Judas Swing setup"""
    timestamp: datetime
    direction: str
    sweep: LiquiditySweep
    entry_price: float
    stop_loss: float
    target: float
    risk_reward: float
    has_sms: bool
    has_fvg: bool


class JudasSwingModel:
    """
    ICT Judas Swing Model
    
    Concept:
    - "Judas" = false move to trap traders before true direction
    - Occurs typically in early session (first 30-60 min)
    - Price sweeps liquidity in one direction, then reverses aggressively
    
    Setup Requirements:
    1. Early session move takes out obvious liquidity
    2. Rejection after sweep (wick, reversal candle)
    3. Displacement in opposite direction
    4. SMS/CHoCH confirming reversal
    
    Entry:
    - After sweep rejection and displacement
    - Enter on FVG or OB in new direction
    - Stop above/below the swept liquidity level
    - Target: Opposite session liquidity
    """
    
    def __init__(
        self,
        pip_size: float = 0.0001,
        sweep_lookback: int = 20,
    ):
        self.pip_size = pip_size
        self.sweep_lookback = sweep_lookback
        
        self.liquidity_detector = LiquidityDetector()
        self.displacement_detector = DisplacementDetector()
        self.fvg_detector = FVGDetector(pip_size=pip_size)
        self.structure_analyzer = MarketStructureAnalyzer()
    
    def scan(self, ohlc: pd.DataFrame) -> Optional[JudasSwingSetup]:
        """
        Scan for Judas Swing setup.
        
        Returns:
            JudasSwingSetup if valid, None otherwise
        """
        self.liquidity_detector.detect(ohlc)
        self.displacement_detector.detect(ohlc)
        self.fvg_detector.detect(ohlc)
        self.structure_analyzer.analyze(ohlc)
        
        recent_sweeps = self.liquidity_detector.get_recent_sweeps(3)
        
        valid_sweep = None
        for sweep in recent_sweeps:
            if sweep.is_rejection:
                valid_sweep = sweep
                break
        
        if not valid_sweep:
            return None
        
        current_price = ohlc.iloc[-1]["close"]
        
        if valid_sweep.liquidity_type == LiquidityType.BUY_SIDE:
            direction = "bearish"
            required_displacement = DisplacementDirection.BEARISH
            fvg_direction = FVGDirection.BEARISH
        else:
            direction = "bullish"
            required_displacement = DisplacementDirection.BULLISH
            fvg_direction = FVGDirection.BULLISH
        
        displacement = self.displacement_detector.get_recent_displacement(
            required_displacement
        )
        if not displacement:
            return None
        
        if displacement.index <= valid_sweep.index:
            return None
        
        last_break = self.structure_analyzer.get_latest_structure_break()
        has_sms = last_break and last_break.break_type.value in ["sms", "choch"]
        
        active_fvgs = self.fvg_detector.get_active_fvgs(fvg_direction)
        has_fvg = len(active_fvgs) > 0
        
        if direction == "bullish":
            entry = current_price
            stop = valid_sweep.sweep_low - (5 * self.pip_size)
            
            bsl = self.liquidity_detector.get_nearest_liquidity(
                current_price, LiquidityType.BUY_SIDE
            )
            target = bsl.level if bsl else ohlc["high"].max()
        else:
            entry = current_price
            stop = valid_sweep.sweep_high + (5 * self.pip_size)
            
            ssl = self.liquidity_detector.get_nearest_liquidity(
                current_price, LiquidityType.SELL_SIDE
            )
            target = ssl.level if ssl else ohlc["low"].min()
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0
        
        if rr < 2.0:
            return None
        
        return JudasSwingSetup(
            timestamp=ohlc.index[-1],
            direction=direction,
            sweep=valid_sweep,
            entry_price=entry,
            stop_loss=stop,
            target=target,
            risk_reward=rr,
            has_sms=has_sms,
            has_fvg=has_fvg,
        )

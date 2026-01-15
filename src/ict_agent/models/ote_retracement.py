"""OTE Retracement Model

Standard ICT retracement entry at Optimal Trade Entry zone.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd
import numpy as np

from ict_agent.detectors.market_structure import MarketStructureAnalyzer, StructureType
from ict_agent.detectors.fvg import FVGDetector, FVGDirection
from ict_agent.detectors.order_block import OrderBlockDetector, OBDirection


@dataclass 
class OTESetup:
    """A valid OTE retracement setup"""
    timestamp: datetime
    direction: str
    swing_high: float
    swing_low: float
    ote_618: float
    ote_705: float
    ote_79: float
    current_price: float
    entry_price: float
    stop_loss: float
    target: float
    risk_reward: float
    in_fvg: bool
    in_ob: bool


class OTERetracementModel:
    """
    ICT Optimal Trade Entry Model
    
    OTE Zone: 61.8% to 79% Fibonacci retracement
    Sweet Spot: 70.5% (most sensitive level)
    
    Setup Requirements:
    1. Clear swing high/low established
    2. BOS or SMS in direction of intended trade
    3. Price retraces into OTE zone
    4. Confluence with FVG or OB preferred
    
    Entry:
    - Limit order at 70.5% or on touch of zone
    - Stop below swing low (longs) or above swing high (shorts)
    - Target: Previous swing or next liquidity
    
    Best Used:
    - After displacement creates new structure
    - During killzones
    - When HTF and LTF aligned
    """
    
    OTE_LEVELS = {
        "fib_618": 0.618,
        "fib_705": 0.705,
        "fib_79": 0.79,
    }
    
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size
        self.structure_analyzer = MarketStructureAnalyzer()
        self.fvg_detector = FVGDetector(pip_size=pip_size)
        self.ob_detector = OrderBlockDetector(pip_size=pip_size)
    
    def calculate_ote_zone(
        self,
        swing_high: float,
        swing_low: float,
        direction: str,
    ) -> dict:
        """
        Calculate OTE zone levels.
        
        For bullish: measure from swing low, OTE is retracement down
        For bearish: measure from swing high, OTE is retracement up
        """
        swing_range = swing_high - swing_low
        
        if direction == "bullish":
            ote_618 = swing_high - (swing_range * self.OTE_LEVELS["fib_618"])
            ote_705 = swing_high - (swing_range * self.OTE_LEVELS["fib_705"])
            ote_79 = swing_high - (swing_range * self.OTE_LEVELS["fib_79"])
        else:
            ote_618 = swing_low + (swing_range * self.OTE_LEVELS["fib_618"])
            ote_705 = swing_low + (swing_range * self.OTE_LEVELS["fib_705"])
            ote_79 = swing_low + (swing_range * self.OTE_LEVELS["fib_79"])
        
        return {
            "ote_618": ote_618,
            "ote_705": ote_705,
            "ote_79": ote_79,
        }
    
    def is_in_ote_zone(
        self,
        price: float,
        swing_high: float,
        swing_low: float,
        direction: str,
    ) -> bool:
        """Check if price is currently in OTE zone"""
        ote = self.calculate_ote_zone(swing_high, swing_low, direction)
        
        if direction == "bullish":
            return ote["ote_79"] <= price <= ote["ote_618"]
        else:
            return ote["ote_618"] <= price <= ote["ote_79"]
    
    def scan(
        self,
        ohlc: pd.DataFrame,
        htf_bias: str,
    ) -> Optional[OTESetup]:
        """
        Scan for OTE retracement setup.
        
        Args:
            ohlc: OHLC data
            htf_bias: "bullish" or "bearish"
        
        Returns:
            OTESetup if valid, None otherwise
        """
        if len(ohlc) < 20:
            return None
        
        self.structure_analyzer.analyze(ohlc)
        self.fvg_detector.detect(ohlc)
        self.ob_detector.detect(ohlc)
        
        swings = self.structure_analyzer.get_protected_swings()
        if len(swings) < 2:
            return None
        
        swing_highs = [s for s in swings if s.swing_type.value == 1]
        swing_lows = [s for s in swings if s.swing_type.value == -1]
        
        if not swing_highs or not swing_lows:
            return None
        
        latest_high = max(swing_highs, key=lambda s: s.index)
        latest_low = max(swing_lows, key=lambda s: s.index)
        
        swing_high = latest_high.price
        swing_low = latest_low.price
        
        current_price = ohlc.iloc[-1]["close"]
        
        if not self.is_in_ote_zone(current_price, swing_high, swing_low, htf_bias):
            return None
        
        ote = self.calculate_ote_zone(swing_high, swing_low, htf_bias)
        
        in_fvg = False
        in_ob = False
        
        if htf_bias == "bullish":
            fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BULLISH)
            obs = self.ob_detector.get_active_order_blocks(OBDirection.BULLISH)
            
            for fvg in fvgs:
                if fvg.contains_price(current_price):
                    in_fvg = True
                    break
            
            for ob in obs:
                if ob.contains_price(current_price):
                    in_ob = True
                    break
            
            entry = ote["ote_705"]
            stop = swing_low - (5 * self.pip_size)
            target = swing_high
        else:
            fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BEARISH)
            obs = self.ob_detector.get_active_order_blocks(OBDirection.BEARISH)
            
            for fvg in fvgs:
                if fvg.contains_price(current_price):
                    in_fvg = True
                    break
            
            for ob in obs:
                if ob.contains_price(current_price):
                    in_ob = True
                    break
            
            entry = ote["ote_705"]
            stop = swing_high + (5 * self.pip_size)
            target = swing_low
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0
        
        if rr < 2.0:
            return None
        
        return OTESetup(
            timestamp=ohlc.index[-1],
            direction=htf_bias,
            swing_high=swing_high,
            swing_low=swing_low,
            ote_618=ote["ote_618"],
            ote_705=ote["ote_705"],
            ote_79=ote["ote_79"],
            current_price=current_price,
            entry_price=entry,
            stop_loss=stop,
            target=target,
            risk_reward=rr,
            in_fvg=in_fvg,
            in_ob=in_ob,
        )

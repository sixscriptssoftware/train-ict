"""Multi-Timeframe Analysis Engine

Implements ICT multi-timeframe workflow:
HTF (Daily/4H) -> ITF (1H) -> LTF (15M/5M)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import numpy as np

from ict_agent.detectors import (
    FVGDetector,
    OrderBlockDetector,
    MarketStructureAnalyzer,
    LiquidityDetector,
    DisplacementDetector,
)
from ict_agent.detectors.market_structure import StructureType
from ict_agent.detectors.fvg import FVGDirection
from ict_agent.detectors.order_block import OBDirection


class Timeframe(Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class Bias(Enum):
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


@dataclass
class TimeframeAnalysis:
    """Analysis results for a single timeframe"""
    timeframe: Timeframe
    trend: StructureType
    bias: Bias
    fvg_count: int
    ob_count: int
    has_displacement: bool
    nearest_bsl: Optional[float]
    nearest_ssl: Optional[float]
    premium_discount: str
    last_structure_break: Optional[str]


@dataclass
class MTFConfluence:
    """Multi-timeframe confluence assessment"""
    htf_bias: Bias
    itf_alignment: bool
    ltf_trigger: bool
    confluence_score: float
    trade_direction: Optional[Bias]
    reasoning: list[str]


class MultiTimeframeAnalyzer:
    """
    Analyzes multiple timeframes for ICT confluence.
    
    ICT MTF Workflow:
    1. HTF (Daily/4H): Establish directional bias
       - Where is draw on liquidity?
       - Are we in premium or discount?
       
    2. ITF (1H): Confirm structure alignment
       - Does 1H structure agree with Daily?
       - Where are key POIs (FVG, OB)?
       
    3. LTF (15M/5M): Find entry trigger
       - Wait for BOS/SMS in direction of HTF bias
       - Enter on FVG or OB within OTE zone
    """
    
    def __init__(self):
        self.fvg_detector = FVGDetector()
        self.ob_detector = OrderBlockDetector()
        self.structure_analyzer = MarketStructureAnalyzer()
        self.liquidity_detector = LiquidityDetector()
        self.displacement_detector = DisplacementDetector()
        
        self._analyses: dict[Timeframe, TimeframeAnalysis] = {}
    
    def analyze_timeframe(
        self, ohlc: pd.DataFrame, timeframe: Timeframe
    ) -> TimeframeAnalysis:
        """Analyze a single timeframe for ICT concepts"""
        structure = self.structure_analyzer.analyze(ohlc)
        fvg = self.fvg_detector.detect(ohlc)
        ob = self.ob_detector.detect(ohlc)
        liquidity = self.liquidity_detector.detect(ohlc)
        displacement = self.displacement_detector.detect(ohlc)
        
        trend = self.structure_analyzer.get_current_trend()
        
        if trend == StructureType.BULLISH:
            bias = Bias.BULLISH
        elif trend == StructureType.BEARISH:
            bias = Bias.BEARISH
        else:
            bias = Bias.NEUTRAL
        
        bullish_fvgs = len(fvg[fvg["fvg_direction"] == 1])
        bearish_fvgs = len(fvg[fvg["fvg_direction"] == -1])
        fvg_count = bullish_fvgs + bearish_fvgs
        
        bullish_obs = len(ob[ob["ob_direction"] == 1])
        bearish_obs = len(ob[ob["ob_direction"] == -1])
        ob_count = bullish_obs + bearish_obs
        
        has_displacement = displacement["is_displacement"].any()
        
        current_price = ohlc.iloc[-1]["close"]
        bsl_pools = self.liquidity_detector.get_active_liquidity()
        nearest_bsl = None
        nearest_ssl = None
        
        bsl_above = [p for p in bsl_pools if p.liquidity_type.value == 1 and p.level > current_price]
        if bsl_above:
            nearest_bsl = min(p.level for p in bsl_above)
        
        ssl_below = [p for p in bsl_pools if p.liquidity_type.value == -1 and p.level < current_price]
        if ssl_below:
            nearest_ssl = max(p.level for p in ssl_below)
        
        swing_high = ohlc["high"].max()
        swing_low = ohlc["low"].min()
        midpoint = (swing_high + swing_low) / 2
        
        if current_price > midpoint:
            premium_discount = "premium"
        else:
            premium_discount = "discount"
        
        last_break = self.structure_analyzer.get_latest_structure_break()
        last_structure_break = last_break.break_type.value if last_break else None
        
        analysis = TimeframeAnalysis(
            timeframe=timeframe,
            trend=trend,
            bias=bias,
            fvg_count=fvg_count,
            ob_count=ob_count,
            has_displacement=has_displacement,
            nearest_bsl=nearest_bsl,
            nearest_ssl=nearest_ssl,
            premium_discount=premium_discount,
            last_structure_break=last_structure_break,
        )
        
        self._analyses[timeframe] = analysis
        return analysis
    
    def analyze_mtf(
        self,
        htf_ohlc: pd.DataFrame,
        itf_ohlc: pd.DataFrame,
        ltf_ohlc: pd.DataFrame,
        htf_timeframe: Timeframe = Timeframe.D1,
        itf_timeframe: Timeframe = Timeframe.H1,
        ltf_timeframe: Timeframe = Timeframe.M15,
    ) -> MTFConfluence:
        """
        Perform complete multi-timeframe analysis.
        
        Returns confluence assessment for trade decision.
        """
        htf_analysis = self.analyze_timeframe(htf_ohlc, htf_timeframe)
        itf_analysis = self.analyze_timeframe(itf_ohlc, itf_timeframe)
        ltf_analysis = self.analyze_timeframe(ltf_ohlc, ltf_timeframe)
        
        htf_bias = htf_analysis.bias
        reasoning = []
        
        if htf_bias == Bias.BULLISH:
            reasoning.append(f"HTF ({htf_timeframe.value}) bias is BULLISH")
        elif htf_bias == Bias.BEARISH:
            reasoning.append(f"HTF ({htf_timeframe.value}) bias is BEARISH")
        else:
            reasoning.append(f"HTF ({htf_timeframe.value}) bias is NEUTRAL - no trade")
        
        itf_alignment = itf_analysis.bias == htf_bias
        if itf_alignment:
            reasoning.append(f"ITF ({itf_timeframe.value}) confirms HTF bias")
        else:
            reasoning.append(f"ITF ({itf_timeframe.value}) does NOT confirm HTF bias")
        
        ltf_trigger = False
        if htf_bias == Bias.BULLISH:
            ltf_trigger = (
                ltf_analysis.last_structure_break in ["bos", "sms"]
                and ltf_analysis.bias == Bias.BULLISH
                and ltf_analysis.has_displacement
            )
            if ltf_analysis.premium_discount == "discount":
                reasoning.append("LTF in discount zone - favorable for longs")
            else:
                reasoning.append("LTF in premium zone - less favorable for longs")
        elif htf_bias == Bias.BEARISH:
            ltf_trigger = (
                ltf_analysis.last_structure_break in ["bos", "sms"]
                and ltf_analysis.bias == Bias.BEARISH
                and ltf_analysis.has_displacement
            )
            if ltf_analysis.premium_discount == "premium":
                reasoning.append("LTF in premium zone - favorable for shorts")
            else:
                reasoning.append("LTF in discount zone - less favorable for shorts")
        
        if ltf_trigger:
            reasoning.append(f"LTF ({ltf_timeframe.value}) shows valid entry trigger")
        else:
            reasoning.append(f"LTF ({ltf_timeframe.value}) no valid entry trigger yet")
        
        score = 0.0
        
        if htf_bias != Bias.NEUTRAL:
            score += 2.0
        
        if itf_alignment:
            score += 1.5
        
        if ltf_trigger:
            score += 2.0
        
        if htf_analysis.has_displacement:
            score += 0.5
        if ltf_analysis.fvg_count > 0:
            score += 0.5
        if ltf_analysis.ob_count > 0:
            score += 0.5
        
        trade_direction = None
        if score >= 4.0 and ltf_trigger:
            trade_direction = htf_bias
        
        return MTFConfluence(
            htf_bias=htf_bias,
            itf_alignment=itf_alignment,
            ltf_trigger=ltf_trigger,
            confluence_score=score,
            trade_direction=trade_direction,
            reasoning=reasoning,
        )
    
    def get_entry_zones(
        self, ohlc: pd.DataFrame, direction: Bias
    ) -> dict:
        """Get potential entry zones (FVGs, OBs) for given direction"""
        self.fvg_detector.detect(ohlc)
        self.ob_detector.detect(ohlc)
        
        if direction == Bias.BULLISH:
            fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BULLISH)
            obs = self.ob_detector.get_active_order_blocks(OBDirection.BULLISH)
        else:
            fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BEARISH)
            obs = self.ob_detector.get_active_order_blocks(OBDirection.BEARISH)
        
        current_price = ohlc.iloc[-1]["close"]
        swing_high = ohlc["high"].max()
        swing_low = ohlc["low"].min()
        
        ote_range = swing_high - swing_low
        ote_618 = swing_low + (ote_range * 0.382) if direction == Bias.BULLISH else swing_high - (ote_range * 0.382)
        ote_705 = swing_low + (ote_range * 0.295) if direction == Bias.BULLISH else swing_high - (ote_range * 0.295)
        ote_79 = swing_low + (ote_range * 0.21) if direction == Bias.BULLISH else swing_high - (ote_range * 0.21)
        
        return {
            "fvgs": [
                {
                    "top": f.top,
                    "bottom": f.bottom,
                    "midpoint": f.midpoint,
                    "timestamp": f.timestamp,
                }
                for f in fvgs
            ],
            "order_blocks": [
                {
                    "high": ob.high,
                    "low": ob.low,
                    "midpoint": ob.midpoint,
                    "timestamp": ob.timestamp,
                }
                for ob in obs
            ],
            "ote_zone": {
                "ote_618": ote_618,
                "ote_705": ote_705,
                "ote_79": ote_79,
            },
            "current_price": current_price,
        }

"""Trading Signal Generator with Model Stacking

Generates trade signals based on ICT models with confluence scoring.
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
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
from ict_agent.detectors.fvg import FVG, FVGDirection
from ict_agent.detectors.order_block import OrderBlock, OBDirection
from ict_agent.detectors.liquidity import LiquidityType
from ict_agent.engine.killzone import KillzoneManager, Killzone
from ict_agent.engine.mtf_analyzer import MultiTimeframeAnalyzer, Bias, Timeframe


class SignalType(Enum):
    LONG = "long"
    SHORT = "short"


class ModelType(Enum):
    SILVER_BULLET = "silver_bullet"
    JUDAS_SWING = "judas_swing"
    OTE_RETRACEMENT = "ote_retracement"
    POWER_OF_THREE = "power_of_three"
    FVG_REBALANCE = "fvg_rebalance"
    LIQUIDITY_SWEEP = "liquidity_sweep"


@dataclass
class Confluences:
    """Track all confluences for a trade signal"""
    fvg: bool = False
    order_block: bool = False
    ote_zone: bool = False
    liquidity_sweep: bool = False
    smt_divergence: bool = False
    displacement: bool = False
    bos_sms: Optional[str] = None
    killzone: bool = False
    macro_time: bool = False
    htf_alignment: bool = False
    premium_discount: bool = False
    
    @property
    def count(self) -> int:
        return sum([
            self.fvg,
            self.order_block,
            self.ote_zone,
            self.liquidity_sweep,
            self.smt_divergence,
            self.displacement,
            self.bos_sms is not None,
            self.killzone,
            self.macro_time,
            self.htf_alignment,
            self.premium_discount,
        ])
    
    def to_dict(self) -> dict:
        return {
            "fvg": self.fvg,
            "order_block": self.order_block,
            "ote_zone": self.ote_zone,
            "liquidity_sweep": self.liquidity_sweep,
            "smt_divergence": self.smt_divergence,
            "displacement": self.displacement,
            "bos_sms": self.bos_sms,
            "killzone": self.killzone,
            "macro_time": self.macro_time,
            "htf_alignment": self.htf_alignment,
            "premium_discount": self.premium_discount,
        }


@dataclass
class TradeSignal:
    """Complete trade signal with all context"""
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    model: ModelType
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: Optional[float]
    risk_reward: float
    confluences: Confluences
    confidence: float
    htf_bias: Bias
    killzone: Optional[Killzone]
    reasoning: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "direction": self.signal_type.value,
            "model": self.model.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "risk_reward": self.risk_reward,
            "confluences": self.confluences.to_dict(),
            "confluence_count": self.confluences.count,
            "confidence": self.confidence,
            "htf_bias": self.htf_bias.value if self.htf_bias else None,
            "killzone": self.killzone.value if self.killzone else None,
            "reasoning": self.reasoning,
        }


class SignalGenerator:
    """
    Generates trade signals using ICT model stacking.
    
    Model Stacking Priority:
    1. Silver Bullet (highest priority - time-based precision)
    2. Judas Swing (reversal after false move)
    3. OTE Retracement (standard continuation)
    4. Power of Three (session-based)
    5. FVG Rebalance (simple gap fill)
    6. Liquidity Sweep (after stop hunt)
    
    Minimum Requirements:
    - HTF bias established
    - In valid killzone OR macro time
    - At least 3 confluences
    - Valid entry zone (FVG, OB, or OTE)
    """
    
    MIN_CONFLUENCES = 3
    MIN_CONFIDENCE = 0.6
    
    def __init__(
        self,
        pip_size: float = 0.0001,
        default_risk_pips: float = 15.0,
        min_rr: float = 2.0,
    ):
        self.pip_size = pip_size
        self.default_risk_pips = default_risk_pips
        self.min_rr = min_rr
        
        self.fvg_detector = FVGDetector(pip_size=pip_size)
        self.ob_detector = OrderBlockDetector(pip_size=pip_size)
        self.structure_analyzer = MarketStructureAnalyzer()
        self.liquidity_detector = LiquidityDetector()
        self.displacement_detector = DisplacementDetector()
        self.killzone_manager = KillzoneManager()
        self.mtf_analyzer = MultiTimeframeAnalyzer()
    
    def generate_signal(
        self,
        symbol: str,
        ltf_ohlc: pd.DataFrame,
        htf_bias: Bias,
        htf_ohlc: Optional[pd.DataFrame] = None,
    ) -> Optional[TradeSignal]:
        """
        Generate a trade signal if conditions are met.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            ltf_ohlc: Low timeframe OHLC data for entry
            htf_bias: Higher timeframe bias (BULLISH/BEARISH)
            htf_ohlc: Optional HTF data for additional analysis
        
        Returns:
            TradeSignal if valid setup found, None otherwise
        """
        if htf_bias == Bias.NEUTRAL:
            return None
        
        current_time = ltf_ohlc.index[-1]
        current_price = ltf_ohlc.iloc[-1]["close"]
        
        structure = self.structure_analyzer.analyze(ltf_ohlc)
        fvg = self.fvg_detector.detect(ltf_ohlc)
        ob = self.ob_detector.detect(ltf_ohlc)
        liquidity = self.liquidity_detector.detect(ltf_ohlc)
        displacement = self.displacement_detector.detect(ltf_ohlc)
        
        confluences = self._build_confluences(
            ltf_ohlc, htf_bias, current_time, current_price
        )
        
        if confluences.count < self.MIN_CONFLUENCES:
            return None
        
        if not (confluences.killzone or confluences.macro_time):
            return None
        
        model = self._determine_model(confluences, current_time)
        
        entry_zone = self._find_entry_zone(ltf_ohlc, htf_bias, current_price)
        if not entry_zone:
            return None
        
        entry_price = entry_zone["entry"]
        stop_loss = entry_zone["stop"]
        
        risk = abs(entry_price - stop_loss)
        target_1 = entry_price + (risk * self.min_rr) if htf_bias == Bias.BULLISH else entry_price - (risk * self.min_rr)
        target_2 = entry_price + (risk * 3.0) if htf_bias == Bias.BULLISH else entry_price - (risk * 3.0)
        
        rr = abs(target_1 - entry_price) / risk if risk > 0 else 0
        
        if rr < self.min_rr:
            return None
        
        confidence = self._calculate_confidence(confluences, model)
        
        if confidence < self.MIN_CONFIDENCE:
            return None
        
        signal_type = SignalType.LONG if htf_bias == Bias.BULLISH else SignalType.SHORT
        killzone = self.killzone_manager.get_current_killzone(current_time)
        
        reasoning = self._build_reasoning(confluences, model, entry_zone)
        
        return TradeSignal(
            timestamp=current_time,
            symbol=symbol,
            signal_type=signal_type,
            model=model,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk_reward=rr,
            confluences=confluences,
            confidence=confidence,
            htf_bias=htf_bias,
            killzone=killzone,
            reasoning=reasoning,
        )
    
    def _build_confluences(
        self,
        ohlc: pd.DataFrame,
        htf_bias: Bias,
        current_time: datetime,
        current_price: float,
    ) -> Confluences:
        """Build confluence object from current market state"""
        confluences = Confluences()
        
        if htf_bias == Bias.BULLISH:
            active_fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BULLISH)
            active_obs = self.ob_detector.get_active_order_blocks(OBDirection.BULLISH)
        else:
            active_fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BEARISH)
            active_obs = self.ob_detector.get_active_order_blocks(OBDirection.BEARISH)
        
        for fvg in active_fvgs:
            if fvg.contains_price(current_price):
                confluences.fvg = True
                break
        
        for ob in active_obs:
            if ob.contains_price(current_price):
                confluences.order_block = True
                break
        
        swing_high = ohlc["high"].max()
        swing_low = ohlc["low"].min()
        swing_range = swing_high - swing_low
        
        if htf_bias == Bias.BULLISH:
            ote_low = swing_low + (swing_range * 0.21)
            ote_high = swing_low + (swing_range * 0.382)
            confluences.ote_zone = ote_low <= current_price <= ote_high
            
            midpoint = (swing_high + swing_low) / 2
            confluences.premium_discount = current_price < midpoint
        else:
            ote_low = swing_high - (swing_range * 0.382)
            ote_high = swing_high - (swing_range * 0.21)
            confluences.ote_zone = ote_low <= current_price <= ote_high
            
            midpoint = (swing_high + swing_low) / 2
            confluences.premium_discount = current_price > midpoint
        
        recent_sweeps = self.liquidity_detector.get_recent_sweeps(3)
        for sweep in recent_sweeps:
            if sweep.is_rejection:
                if htf_bias == Bias.BULLISH and sweep.liquidity_type == LiquidityType.SELL_SIDE:
                    confluences.liquidity_sweep = True
                    break
                elif htf_bias == Bias.BEARISH and sweep.liquidity_type == LiquidityType.BUY_SIDE:
                    confluences.liquidity_sweep = True
                    break
        
        recent_displacement = self.displacement_detector.get_recent_displacement()
        if recent_displacement:
            if htf_bias == Bias.BULLISH and recent_displacement.direction.value == 1:
                confluences.displacement = True
            elif htf_bias == Bias.BEARISH and recent_displacement.direction.value == -1:
                confluences.displacement = True
        
        last_break = self.structure_analyzer.get_latest_structure_break()
        if last_break:
            confluences.bos_sms = last_break.break_type.value
        
        confluences.killzone = self.killzone_manager.is_primary_killzone(current_time)
        confluences.macro_time = self.killzone_manager.is_in_macro_time(current_time)
        
        current_trend = self.structure_analyzer.get_current_trend()
        if htf_bias == Bias.BULLISH and current_trend == StructureType.BULLISH:
            confluences.htf_alignment = True
        elif htf_bias == Bias.BEARISH and current_trend == StructureType.BEARISH:
            confluences.htf_alignment = True
        
        return confluences
    
    def _determine_model(
        self, confluences: Confluences, current_time: datetime
    ) -> ModelType:
        """Determine which ICT model best fits the setup"""
        if self.killzone_manager.is_silver_bullet_window(current_time):
            if confluences.fvg and confluences.displacement:
                return ModelType.SILVER_BULLET
        
        if confluences.liquidity_sweep and confluences.displacement:
            return ModelType.JUDAS_SWING
        
        if confluences.ote_zone and confluences.htf_alignment:
            return ModelType.OTE_RETRACEMENT
        
        if confluences.fvg:
            return ModelType.FVG_REBALANCE
        
        if confluences.liquidity_sweep:
            return ModelType.LIQUIDITY_SWEEP
        
        return ModelType.OTE_RETRACEMENT
    
    def _find_entry_zone(
        self,
        ohlc: pd.DataFrame,
        htf_bias: Bias,
        current_price: float,
    ) -> Optional[dict]:
        """Find valid entry zone with stop loss"""
        if htf_bias == Bias.BULLISH:
            active_fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BULLISH)
            active_obs = self.ob_detector.get_active_order_blocks(OBDirection.BULLISH)
            
            entry_zones = []
            
            for fvg in active_fvgs:
                if fvg.bottom < current_price:
                    entry_zones.append({
                        "entry": fvg.midpoint,
                        "stop": fvg.bottom - (self.default_risk_pips * self.pip_size),
                        "type": "fvg",
                    })
            
            for ob in active_obs:
                if ob.low < current_price:
                    entry_zones.append({
                        "entry": ob.midpoint,
                        "stop": ob.low - (5 * self.pip_size),
                        "type": "ob",
                    })
            
            if not entry_zones:
                swing_low = ohlc["low"].min()
                swing_high = ohlc["high"].max()
                ote_705 = swing_low + ((swing_high - swing_low) * 0.295)
                
                entry_zones.append({
                    "entry": ote_705,
                    "stop": swing_low - (5 * self.pip_size),
                    "type": "ote",
                })
            
            return min(entry_zones, key=lambda z: abs(z["entry"] - current_price))
        
        else:
            active_fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BEARISH)
            active_obs = self.ob_detector.get_active_order_blocks(OBDirection.BEARISH)
            
            entry_zones = []
            
            for fvg in active_fvgs:
                if fvg.top > current_price:
                    entry_zones.append({
                        "entry": fvg.midpoint,
                        "stop": fvg.top + (self.default_risk_pips * self.pip_size),
                        "type": "fvg",
                    })
            
            for ob in active_obs:
                if ob.high > current_price:
                    entry_zones.append({
                        "entry": ob.midpoint,
                        "stop": ob.high + (5 * self.pip_size),
                        "type": "ob",
                    })
            
            if not entry_zones:
                swing_low = ohlc["low"].min()
                swing_high = ohlc["high"].max()
                ote_705 = swing_high - ((swing_high - swing_low) * 0.295)
                
                entry_zones.append({
                    "entry": ote_705,
                    "stop": swing_high + (5 * self.pip_size),
                    "type": "ote",
                })
            
            return min(entry_zones, key=lambda z: abs(z["entry"] - current_price))
    
    def _calculate_confidence(
        self, confluences: Confluences, model: ModelType
    ) -> float:
        """Calculate confidence score (0-1) for the signal"""
        base_score = confluences.count / 11.0
        
        model_bonus = {
            ModelType.SILVER_BULLET: 0.15,
            ModelType.JUDAS_SWING: 0.12,
            ModelType.OTE_RETRACEMENT: 0.10,
            ModelType.POWER_OF_THREE: 0.08,
            ModelType.FVG_REBALANCE: 0.05,
            ModelType.LIQUIDITY_SWEEP: 0.08,
        }
        
        score = base_score + model_bonus.get(model, 0)
        
        if confluences.htf_alignment:
            score += 0.1
        if confluences.displacement:
            score += 0.08
        if confluences.killzone and confluences.macro_time:
            score += 0.05
        
        return min(score, 1.0)
    
    def _build_reasoning(
        self,
        confluences: Confluences,
        model: ModelType,
        entry_zone: dict,
    ) -> list[str]:
        """Build human-readable reasoning for the signal"""
        reasoning = []
        
        reasoning.append(f"Model: {model.value}")
        reasoning.append(f"Entry zone type: {entry_zone['type']}")
        reasoning.append(f"Confluences: {confluences.count}/11")
        
        if confluences.htf_alignment:
            reasoning.append("HTF structure aligned")
        if confluences.fvg:
            reasoning.append("Price in FVG zone")
        if confluences.order_block:
            reasoning.append("Price at Order Block")
        if confluences.ote_zone:
            reasoning.append("Price in OTE zone (61.8-79%)")
        if confluences.liquidity_sweep:
            reasoning.append("Recent liquidity sweep with rejection")
        if confluences.displacement:
            reasoning.append("Valid displacement present")
        if confluences.bos_sms:
            reasoning.append(f"Structure break: {confluences.bos_sms.upper()}")
        if confluences.killzone:
            reasoning.append("In primary killzone")
        if confluences.macro_time:
            reasoning.append("In macro time window")
        
        return reasoning

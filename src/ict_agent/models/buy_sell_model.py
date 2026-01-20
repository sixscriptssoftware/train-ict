"""ICT Buy/Sell Model Framework

The MACRO framework that governs all ICT trading. All other concepts (FVG, OB, MSS)
are tools that operate WITHIN this framework.

Buy Model (Bullish):
- Accumulation → Manipulation (Judas down) → Distribution (expansion up)
- Targets: External Range Liquidity (old highs, equal highs)

Sell Model (Bearish):
- Accumulation → Manipulation (Judas up) → Distribution (expansion down)  
- Targets: External Range Liquidity (old lows, equal lows)

Leg Structure:
- L1: First accumulation/distribution phase
- L2: Reaccumulation/redistribution (the "trap")
- L3/Terminus: Final leg to the target
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, List, Tuple
import pandas as pd
import numpy as np

from ict_agent.detectors.market_structure import (
    MarketStructureAnalyzer,
    StructureType,
    SwingPoint,
    SwingType,
)
from ict_agent.detectors.fvg import FVGDetector, FVG, FVGDirection
from ict_agent.detectors.displacement import DisplacementDetector


class ModelType(Enum):
    BUY_MODEL = "buy_model"
    SELL_MODEL = "sell_model"


class ModelPhase(Enum):
    ACCUMULATION = "accumulation"
    MANIPULATION = "manipulation"  # Judas swing
    DISTRIBUTION = "distribution"
    COMPLETE = "complete"


class LegType(Enum):
    L1 = "L1"  # First leg
    L2 = "L2"  # Reaccumulation/redistribution
    L3 = "L3"  # Final leg / Terminus
    TERMINUS = "terminus"  # The reversal point


@dataclass
class LiquidityLevel:
    """Represents a liquidity level (ERL or IRL)"""
    price: float
    level_type: str  # "equal_highs", "equal_lows", "old_high", "old_low", "fvg", "ob"
    is_external: bool  # True = ERL, False = IRL
    timestamp: pd.Timestamp
    swept: bool = False
    swept_at: Optional[pd.Timestamp] = None


@dataclass
class ModelLeg:
    """Represents a leg in the Buy/Sell Model"""
    leg_type: LegType
    start_index: int
    end_index: Optional[int]
    start_price: float
    end_price: Optional[float]
    start_time: pd.Timestamp
    end_time: Optional[pd.Timestamp]
    high: float
    low: float
    fvgs_in_leg: List[FVG] = field(default_factory=list)
    is_complete: bool = False


@dataclass
class AccDisZone:
    """Accumulation turns Distribution zone"""
    zone_type: str  # "acc_turn_dis" or "dis_turn_acc"
    top: float
    bottom: float
    midpoint: float
    start_time: pd.Timestamp
    end_time: Optional[pd.Timestamp]
    leg_association: LegType
    mitigated: bool = False


@dataclass
class BuySellModelState:
    """Complete state of a Buy/Sell Model"""
    model_type: ModelType
    phase: ModelPhase
    legs: List[ModelLeg] = field(default_factory=list)
    acc_dis_zones: List[AccDisZone] = field(default_factory=list)
    terminus_price: Optional[float] = None
    terminus_time: Optional[pd.Timestamp] = None
    target_liquidity: Optional[LiquidityLevel] = None
    draw_on_liquidity: Optional[float] = None
    is_valid: bool = True
    confidence: float = 0.0
    
    @property
    def current_leg(self) -> Optional[ModelLeg]:
        if self.legs:
            return self.legs[-1]
        return None
    
    @property
    def leg_count(self) -> int:
        return len(self.legs)


class BuySellModelDetector:
    """
    Detects and tracks ICT Buy/Sell Model formations.
    
    The Buy/Sell Model is the MACRO framework:
    
    SELL MODEL (Bearish):
    1. Price accumulates (consolidation)
    2. Manipulation: Judas swing UP to sweep buy-side liquidity
    3. Terminus: Smart money reversal (THE HIGH)
    4. Distribution: L1 → L2 → L3 moving lower
    5. Each leg creates "ACC turn DIS" zones
    6. Target: External Range Liquidity (old lows, equal lows)
    
    BUY MODEL (Bullish):
    1. Price accumulates (consolidation)
    2. Manipulation: Judas swing DOWN to sweep sell-side liquidity
    3. Terminus: Smart money reversal (THE LOW)
    4. Distribution: L1 → L2 → L3 moving higher
    5. Each leg creates "DIS turn ACC" zones
    6. Target: External Range Liquidity (old highs, equal highs)
    """
    
    def __init__(
        self,
        swing_length: int = 10,
        min_leg_pips: float = 20.0,
        pip_size: float = 0.0001,
        acc_dis_threshold: float = 0.382,  # Fib level for zone detection
    ):
        self.swing_length = swing_length
        self.min_leg_pips = min_leg_pips
        self.pip_size = pip_size
        self.acc_dis_threshold = acc_dis_threshold
        
        self.structure_analyzer = MarketStructureAnalyzer(swing_length=swing_length)
        self.fvg_detector = FVGDetector(pip_size=pip_size)
        
        self._current_model: Optional[BuySellModelState] = None
        self._liquidity_levels: List[LiquidityLevel] = []
    
    def analyze(
        self,
        ohlc: pd.DataFrame,
        htf_bias: Optional[str] = None,
    ) -> Optional[BuySellModelState]:
        """
        Analyze price data for Buy/Sell Model formation.
        
        Args:
            ohlc: OHLCV DataFrame with DatetimeIndex
            htf_bias: Optional higher timeframe bias ("bullish" or "bearish")
        
        Returns:
            BuySellModelState if model detected, None otherwise
        """
        if len(ohlc) < self.swing_length * 3:
            return None
        
        # Analyze market structure
        structure_df = self.structure_analyzer.analyze(ohlc)
        swings = self.structure_analyzer._swings  # Access internal swings list
        
        # Detect FVGs
        fvg_df = self.fvg_detector.detect(ohlc)
        
        # Identify liquidity levels
        self._identify_liquidity_levels(ohlc, swings)
        
        # Detect model based on structure
        model = self._detect_model(ohlc, swings, htf_bias)
        
        if model:
            # Identify legs
            self._identify_legs(ohlc, model, swings)
            
            # Identify ACC/DIS zones
            self._identify_acc_dis_zones(ohlc, model)
            
            # Set target liquidity
            self._set_target_liquidity(model)
            
            # Calculate confidence
            model.confidence = self._calculate_confidence(model)
            
            self._current_model = model
        
        return model
    
    def _detect_model(
        self,
        ohlc: pd.DataFrame,
        swings: List[SwingPoint],
        htf_bias: Optional[str],
    ) -> Optional[BuySellModelState]:
        """Detect if we're in a Buy or Sell model"""
        
        if len(swings) < 4:
            return None
        
        recent_swings = swings[-10:]  # Look at last 10 swings
        
        # Check for Sell Model: HH followed by structural break down
        # Pattern: HL → HH (terminus) → LH → LL (confirmation)
        sell_model = self._check_sell_model_formation(recent_swings, ohlc)
        if sell_model:
            return sell_model
        
        # Check for Buy Model: LL followed by structural break up
        # Pattern: LH → LL (terminus) → HL → HH (confirmation)
        buy_model = self._check_buy_model_formation(recent_swings, ohlc)
        if buy_model:
            return buy_model
        
        # If HTF bias provided, look for forming model
        if htf_bias == "bearish":
            return self._check_forming_sell_model(recent_swings, ohlc)
        elif htf_bias == "bullish":
            return self._check_forming_buy_model(recent_swings, ohlc)
        
        return None
    
    def _check_sell_model_formation(
        self,
        swings: List[SwingPoint],
        ohlc: pd.DataFrame,
    ) -> Optional[BuySellModelState]:
        """Check for confirmed Sell Model"""
        
        # Find potential terminus (highest high after accumulation)
        highs = [s for s in swings if s.swing_type == SwingType.HIGH]
        lows = [s for s in swings if s.swing_type == SwingType.LOW]
        
        if len(highs) < 2 or len(lows) < 2:
            return None
        
        # Look for HH that gets followed by LH and LL (structure break)
        for i in range(len(highs) - 1):
            potential_terminus = highs[i]
            
            # Check if there's a lower high after this
            later_highs = [h for h in highs if h.index > potential_terminus.index]
            later_lows = [l for l in lows if l.index > potential_terminus.index]
            
            if not later_highs or not later_lows:
                continue
            
            # Is the next high lower? (LH confirmation)
            if later_highs[0].price < potential_terminus.price:
                # Is there a lower low? (Structure break confirmation)
                pre_terminus_lows = [l for l in lows if l.index < potential_terminus.index]
                if pre_terminus_lows:
                    last_hl = pre_terminus_lows[-1]
                    
                    # Check if we broke below the HL
                    if later_lows[0].price < last_hl.price:
                        # SELL MODEL CONFIRMED
                        return BuySellModelState(
                            model_type=ModelType.SELL_MODEL,
                            phase=ModelPhase.DISTRIBUTION,
                            terminus_price=potential_terminus.price,
                            terminus_time=potential_terminus.timestamp,
                            is_valid=True,
                        )
        
        return None
    
    def _check_buy_model_formation(
        self,
        swings: List[SwingPoint],
        ohlc: pd.DataFrame,
    ) -> Optional[BuySellModelState]:
        """Check for confirmed Buy Model"""
        
        highs = [s for s in swings if s.swing_type == SwingType.HIGH]
        lows = [s for s in swings if s.swing_type == SwingType.LOW]
        
        if len(highs) < 2 or len(lows) < 2:
            return None
        
        # Look for LL that gets followed by HL and HH (structure break)
        for i in range(len(lows) - 1):
            potential_terminus = lows[i]
            
            later_lows = [l for l in lows if l.index > potential_terminus.index]
            later_highs = [h for h in highs if h.index > potential_terminus.index]
            
            if not later_lows or not later_highs:
                continue
            
            # Is the next low higher? (HL confirmation)
            if later_lows[0].price > potential_terminus.price:
                # Is there a higher high? (Structure break confirmation)
                pre_terminus_highs = [h for h in highs if h.index < potential_terminus.index]
                if pre_terminus_highs:
                    last_lh = pre_terminus_highs[-1]
                    
                    if later_highs[0].price > last_lh.price:
                        # BUY MODEL CONFIRMED
                        return BuySellModelState(
                            model_type=ModelType.BUY_MODEL,
                            phase=ModelPhase.DISTRIBUTION,
                            terminus_price=potential_terminus.price,
                            terminus_time=potential_terminus.timestamp,
                            is_valid=True,
                        )
        
        return None
    
    def _check_forming_sell_model(
        self,
        swings: List[SwingPoint],
        ohlc: pd.DataFrame,
    ) -> Optional[BuySellModelState]:
        """Check for forming (not yet confirmed) Sell Model"""
        
        highs = [s for s in swings if s.swing_type == SwingType.HIGH]
        
        if not highs:
            return None
        
        # The most recent significant high could be the terminus
        recent_high = max(highs[-3:], key=lambda x: x.price) if len(highs) >= 3 else highs[-1]
        current_price = ohlc['close'].iloc[-1]
        
        # If price is below the recent high, we might be in manipulation/distribution
        if current_price < recent_high.price:
            return BuySellModelState(
                model_type=ModelType.SELL_MODEL,
                phase=ModelPhase.MANIPULATION,  # Still forming
                terminus_price=recent_high.price,
                terminus_time=recent_high.timestamp,
                is_valid=True,
            )
        
        return None
    
    def _check_forming_buy_model(
        self,
        swings: List[SwingPoint],
        ohlc: pd.DataFrame,
    ) -> Optional[BuySellModelState]:
        """Check for forming (not yet confirmed) Buy Model"""
        
        lows = [s for s in swings if s.swing_type == SwingType.LOW]
        
        if not lows:
            return None
        
        recent_low = min(lows[-3:], key=lambda x: x.price) if len(lows) >= 3 else lows[-1]
        current_price = ohlc['close'].iloc[-1]
        
        if current_price > recent_low.price:
            return BuySellModelState(
                model_type=ModelType.BUY_MODEL,
                phase=ModelPhase.MANIPULATION,
                terminus_price=recent_low.price,
                terminus_time=recent_low.timestamp,
                is_valid=True,
            )
        
        return None
    
    def _identify_legs(
        self,
        ohlc: pd.DataFrame,
        model: BuySellModelState,
        swings: List[SwingPoint],
    ) -> None:
        """Identify L1, L2, L3 legs in the model"""
        
        if model.terminus_time is None:
            return
        
        terminus_idx = ohlc.index.get_loc(model.terminus_time) if model.terminus_time in ohlc.index else None
        if terminus_idx is None:
            # Find closest index
            terminus_idx = ohlc.index.searchsorted(model.terminus_time)
        
        post_terminus_swings = [s for s in swings if s.index > terminus_idx]
        
        if model.model_type == ModelType.SELL_MODEL:
            # For sell model, legs are defined by swing lows (distribution points)
            swing_lows = [s for s in post_terminus_swings if s.swing_type == SwingType.LOW]
            swing_highs = [s for s in post_terminus_swings if s.swing_type == SwingType.HIGH]
            
            self._create_legs_from_swings(ohlc, model, swing_lows, swing_highs, is_sell=True)
        else:
            # For buy model, legs are defined by swing highs (distribution points)
            swing_lows = [s for s in post_terminus_swings if s.swing_type == SwingType.LOW]
            swing_highs = [s for s in post_terminus_swings if s.swing_type == SwingType.HIGH]
            
            self._create_legs_from_swings(ohlc, model, swing_highs, swing_lows, is_sell=False)
    
    def _create_legs_from_swings(
        self,
        ohlc: pd.DataFrame,
        model: BuySellModelState,
        primary_swings: List[SwingPoint],
        secondary_swings: List[SwingPoint],
        is_sell: bool,
    ) -> None:
        """Create leg structures from swing points"""
        
        leg_types = [LegType.L1, LegType.L2, LegType.L3]
        
        # Start from terminus
        prev_price = model.terminus_price
        prev_time = model.terminus_time
        prev_idx = ohlc.index.get_loc(prev_time) if prev_time in ohlc.index else 0
        
        for i, swing in enumerate(primary_swings[:3]):  # Max 3 legs
            leg = ModelLeg(
                leg_type=leg_types[i] if i < 3 else LegType.L3,
                start_index=prev_idx,
                end_index=swing.index,
                start_price=prev_price,
                end_price=swing.price,
                start_time=prev_time,
                end_time=swing.timestamp,
                high=max(prev_price, swing.price),
                low=min(prev_price, swing.price),
                is_complete=True,
            )
            
            # Find FVGs within this leg
            leg.fvgs_in_leg = self._find_fvgs_in_range(
                prev_idx, swing.index, 
                FVGDirection.BEARISH if is_sell else FVGDirection.BULLISH
            )
            
            model.legs.append(leg)
            
            prev_price = swing.price
            prev_time = swing.timestamp
            prev_idx = swing.index
    
    def _find_fvgs_in_range(
        self,
        start_idx: int,
        end_idx: int,
        direction: FVGDirection,
    ) -> List[FVG]:
        """Find FVGs within an index range"""
        fvgs = self.fvg_detector.get_active_fvgs(direction)
        return [f for f in fvgs if start_idx <= f.index <= end_idx]
    
    def _identify_acc_dis_zones(
        self,
        ohlc: pd.DataFrame,
        model: BuySellModelState,
    ) -> None:
        """Identify ACC turn DIS zones between legs"""
        
        for i, leg in enumerate(model.legs):
            if not leg.is_complete:
                continue
            
            # The consolidation between legs is an ACC/DIS zone
            if i < len(model.legs) - 1:
                next_leg = model.legs[i + 1]
                
                # Zone is between end of this leg and start of next leg's movement
                zone_high = max(leg.end_price, next_leg.start_price)
                zone_low = min(leg.end_price, next_leg.start_price)
                
                # Expand zone to include wicks in that range
                zone_range = ohlc.iloc[leg.end_index:next_leg.start_index + 1]
                if len(zone_range) > 0:
                    zone_high = max(zone_high, zone_range['high'].max())
                    zone_low = min(zone_low, zone_range['low'].min())
                
                zone = AccDisZone(
                    zone_type="acc_turn_dis" if model.model_type == ModelType.SELL_MODEL else "dis_turn_acc",
                    top=zone_high,
                    bottom=zone_low,
                    midpoint=(zone_high + zone_low) / 2,
                    start_time=leg.end_time,
                    end_time=next_leg.start_time,
                    leg_association=leg.leg_type,
                )
                
                model.acc_dis_zones.append(zone)
    
    def _identify_liquidity_levels(
        self,
        ohlc: pd.DataFrame,
        swings: List[SwingPoint],
    ) -> None:
        """Identify External and Internal Range Liquidity levels"""
        
        self._liquidity_levels = []
        
        # External Range Liquidity: Equal highs/lows, old swing points
        highs = [s for s in swings if s.swing_type == SwingType.HIGH]
        lows = [s for s in swings if s.swing_type == SwingType.LOW]
        
        # Find equal highs (buy-side liquidity)
        for i in range(len(highs) - 1):
            for j in range(i + 1, len(highs)):
                if abs(highs[i].price - highs[j].price) < 10 * self.pip_size:
                    self._liquidity_levels.append(LiquidityLevel(
                        price=max(highs[i].price, highs[j].price),
                        level_type="equal_highs",
                        is_external=True,
                        timestamp=highs[j].timestamp,
                    ))
                    break
        
        # Find equal lows (sell-side liquidity)
        for i in range(len(lows) - 1):
            for j in range(i + 1, len(lows)):
                if abs(lows[i].price - lows[j].price) < 10 * self.pip_size:
                    self._liquidity_levels.append(LiquidityLevel(
                        price=min(lows[i].price, lows[j].price),
                        level_type="equal_lows",
                        is_external=True,
                        timestamp=lows[j].timestamp,
                    ))
                    break
    
    def _set_target_liquidity(self, model: BuySellModelState) -> None:
        """Set the target liquidity level for the model"""
        
        if model.model_type == ModelType.SELL_MODEL:
            # Target sell-side liquidity (equal lows, old lows)
            ssl_levels = [l for l in self._liquidity_levels 
                         if l.level_type in ("equal_lows", "old_low") and l.is_external]
            if ssl_levels:
                # Find the nearest SSL below current price
                model.target_liquidity = min(ssl_levels, key=lambda x: x.price)
                model.draw_on_liquidity = model.target_liquidity.price
        else:
            # Target buy-side liquidity (equal highs, old highs)
            bsl_levels = [l for l in self._liquidity_levels
                         if l.level_type in ("equal_highs", "old_high") and l.is_external]
            if bsl_levels:
                model.target_liquidity = max(bsl_levels, key=lambda x: x.price)
                model.draw_on_liquidity = model.target_liquidity.price
    
    def _calculate_confidence(self, model: BuySellModelState) -> float:
        """Calculate confidence score for the model"""
        
        score = 0.0
        
        # Has terminus identified
        if model.terminus_price:
            score += 0.2
        
        # Has at least one leg
        if model.leg_count >= 1:
            score += 0.15
        if model.leg_count >= 2:
            score += 0.15
        if model.leg_count >= 3:
            score += 0.1
        
        # Has ACC/DIS zones
        if model.acc_dis_zones:
            score += 0.15
        
        # Has target liquidity
        if model.target_liquidity:
            score += 0.15
        
        # Phase is distribution (confirmed)
        if model.phase == ModelPhase.DISTRIBUTION:
            score += 0.1
        
        return min(score, 1.0)
    
    def get_current_model(self) -> Optional[BuySellModelState]:
        """Get the current model state"""
        return self._current_model
    
    def get_entry_zones(self, model: BuySellModelState) -> List[AccDisZone]:
        """Get potential entry zones (ACC turn DIS zones that haven't been mitigated)"""
        return [z for z in model.acc_dis_zones if not z.mitigated]
    
    def get_active_liquidity(self) -> List[LiquidityLevel]:
        """Get all active (unswept) liquidity levels"""
        return [l for l in self._liquidity_levels if not l.swept]

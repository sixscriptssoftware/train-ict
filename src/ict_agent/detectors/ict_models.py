"""
ICT Models Detector

- Power of 3 (AMD - Accumulation, Manipulation, Distribution)
- Market Maker Buy/Sell Model
- Unicorn Model (OB + FVG overlap)
- 2022 Model
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import pytz


@dataclass
class PowerOfThree:
    """
    Power of 3 / AMD Model
    
    Accumulation: Range forms (usually Asian session)
    Manipulation: False breakout (Judas swing)
    Distribution: Real move in opposite direction
    """
    phase: Literal["ACCUMULATION", "MANIPULATION", "DISTRIBUTION"]
    accumulation_high: float
    accumulation_low: float
    manipulation_direction: Optional[Literal["BULLISH", "BEARISH"]]  # Direction of fake move
    expected_distribution: Optional[Literal["LONG", "SHORT"]]  # Expected trade direction
    confidence: float  # 0-100


@dataclass
class MarketMakerModel:
    """
    Market Maker Buy Model (MMBM) or Market Maker Sell Model (MMSM)
    
    MMBM: Smart money accumulating longs
    - Original Consolidation
    - Smart Money Reversal (sweep low)
    - Smart Money Reversal Low (lowest point)
    - Reaccumulation
    - Distribution
    
    MMSM: Smart money accumulating shorts
    - Same structure inverted
    """
    model_type: Literal["MMBM", "MMSM"]
    phase: Literal["ORIGINAL_CONSOLIDATION", "SMART_MONEY_REVERSAL", "REACCUMULATION", "DISTRIBUTION"]
    reversal_point: float
    current_price: float
    target: float


@dataclass
class UnicornModel:
    """
    Unicorn Model = Order Block + Fair Value Gap overlap
    
    When an OB and FVG align at the same level, it's a high probability entry.
    """
    direction: Literal["BULLISH", "BEARISH"]
    ob_top: float
    ob_bottom: float
    fvg_top: float
    fvg_bottom: float
    overlap_top: float
    overlap_bottom: float
    ce: float  # Consequent encroachment of overlap
    strength: Literal["WEAK", "MODERATE", "STRONG"]


@dataclass
class Model2022:
    """
    ICT 2022 Model - Specific entry pattern
    
    1. Identify HTF direction (Daily/4H bias)
    2. Wait for sweep of liquidity
    3. Look for FVG or OB for entry
    4. Enter on LTF confirmation
    5. Target opposite liquidity
    """
    htf_bias: Literal["BULLISH", "BEARISH"]
    liquidity_swept: Literal["BSL", "SSL"]
    sweep_price: float
    entry_zone_type: Literal["FVG", "OB", "UNICORN"]
    entry_zone: tuple  # (bottom, top)
    target: float
    stop_loss: float
    valid: bool


class ICTModelDetector:
    """
    Detects ICT trading models and setups.
    """
    
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size
        self.et = pytz.timezone('America/New_York')
    
    def detect_po3(self, ohlc: pd.DataFrame) -> PowerOfThree:
        """
        Detect Power of 3 (AMD) phase.
        
        Uses time and price structure to determine current phase.
        """
        # Get time context
        try:
            ts = ohlc.index[-1]
            if ts.tzinfo is None:
                ts = ts.tz_localize('UTC')
            et_time = ts.astimezone(self.et)
            hour = et_time.hour
        except:
            hour = 12  # Default to neutral
        
        # Get recent range
        recent = ohlc.iloc[-48:]  # Last ~12 hours on 15m
        range_high = recent['high'].max()
        range_low = recent['low'].min()
        
        # Determine phase based on time
        if 19 <= hour or hour < 2:
            # Asian session = Accumulation
            phase = "ACCUMULATION"
            manipulation_dir = None
            expected_dist = None
            confidence = 70
        elif 2 <= hour < 8:
            # London session = Manipulation
            phase = "MANIPULATION"
            
            # Check which side got swept
            current_price = ohlc['close'].iloc[-1]
            asian_high = ohlc.iloc[-20:-8]['high'].max() if len(ohlc) > 20 else range_high
            asian_low = ohlc.iloc[-20:-8]['low'].min() if len(ohlc) > 20 else range_low
            
            if current_price > asian_high:
                manipulation_dir = "BULLISH"
                expected_dist = "SHORT"  # Expect reversal down
            elif current_price < asian_low:
                manipulation_dir = "BEARISH"
                expected_dist = "LONG"  # Expect reversal up
            else:
                manipulation_dir = None
                expected_dist = None
            
            confidence = 60
        else:
            # NY session = Distribution
            phase = "DISTRIBUTION"
            
            # Determine direction of distribution
            london_high = ohlc.iloc[-24:-8]['high'].max() if len(ohlc) > 24 else range_high
            london_low = ohlc.iloc[-24:-8]['low'].min() if len(ohlc) > 24 else range_low
            current = ohlc['close'].iloc[-1]
            
            if current > london_high:
                manipulation_dir = "BULLISH"
                expected_dist = "LONG"  # Continuation
            elif current < london_low:
                manipulation_dir = "BEARISH"
                expected_dist = "SHORT"
            else:
                manipulation_dir = None
                expected_dist = None
            
            confidence = 80
        
        return PowerOfThree(
            phase=phase,
            accumulation_high=range_high,
            accumulation_low=range_low,
            manipulation_direction=manipulation_dir,
            expected_distribution=expected_dist,
            confidence=confidence
        )
    
    def detect_unicorn(
        self, 
        order_blocks: List[dict],
        fvgs: List[dict]
    ) -> List[UnicornModel]:
        """
        Detect Unicorn setups (OB + FVG overlap).
        
        Args:
            order_blocks: List of OBs with 'direction', 'top', 'bottom'
            fvgs: List of FVGs with 'direction', 'top', 'bottom'
        """
        unicorns = []
        
        for ob in order_blocks:
            for fvg in fvgs:
                # Must be same direction
                if ob.get('direction') != fvg.get('direction'):
                    continue
                
                # Check for overlap
                ob_top = ob.get('top', 0)
                ob_bottom = ob.get('bottom', 0)
                fvg_top = fvg.get('top', 0)
                fvg_bottom = fvg.get('bottom', 0)
                
                # Calculate overlap
                overlap_bottom = max(ob_bottom, fvg_bottom)
                overlap_top = min(ob_top, fvg_top)
                
                if overlap_top > overlap_bottom:
                    # There is overlap!
                    overlap_size = overlap_top - overlap_bottom
                    ob_size = ob_top - ob_bottom
                    fvg_size = fvg_top - fvg_bottom
                    
                    # Determine strength based on overlap percentage
                    overlap_pct = overlap_size / min(ob_size, fvg_size) * 100
                    
                    if overlap_pct >= 70:
                        strength = "STRONG"
                    elif overlap_pct >= 40:
                        strength = "MODERATE"
                    else:
                        strength = "WEAK"
                    
                    unicorns.append(UnicornModel(
                        direction=ob.get('direction'),
                        ob_top=ob_top,
                        ob_bottom=ob_bottom,
                        fvg_top=fvg_top,
                        fvg_bottom=fvg_bottom,
                        overlap_top=overlap_top,
                        overlap_bottom=overlap_bottom,
                        ce=(overlap_top + overlap_bottom) / 2,
                        strength=strength
                    ))
        
        return unicorns
    
    def detect_2022_model(
        self,
        ohlc: pd.DataFrame,
        htf_bias: Literal["BULLISH", "BEARISH"],
        recent_sweep: dict = None,
        entry_zones: List[dict] = None
    ) -> Optional[Model2022]:
        """
        Detect 2022 Model setup.
        
        Requires:
        1. HTF bias (from higher timeframe analysis)
        2. Recent liquidity sweep
        3. Entry zone (FVG or OB)
        """
        if not recent_sweep or not entry_zones:
            return None
        
        current_price = ohlc['close'].iloc[-1]
        
        # Check if sweep aligns with bias
        sweep_type = recent_sweep.get('type', '')
        
        if htf_bias == "BULLISH" and 'SSL' in sweep_type:
            # Good - swept sell-side in bullish bias
            valid = True
            target = ohlc['high'].iloc[-20:].max()  # BSL target
        elif htf_bias == "BEARISH" and 'BSL' in sweep_type:
            # Good - swept buy-side in bearish bias
            valid = True
            target = ohlc['low'].iloc[-20:].min()  # SSL target
        else:
            valid = False
            target = current_price
        
        # Find best entry zone
        best_zone = None
        zone_type = "FVG"
        
        for zone in entry_zones:
            zone_dir = zone.get('direction', '')
            if htf_bias == "BULLISH" and 'BULL' in str(zone_dir):
                best_zone = (zone.get('bottom', 0), zone.get('top', 0))
                zone_type = zone.get('type', 'FVG')
                break
            elif htf_bias == "BEARISH" and 'BEAR' in str(zone_dir):
                best_zone = (zone.get('bottom', 0), zone.get('top', 0))
                zone_type = zone.get('type', 'FVG')
                break
        
        if not best_zone:
            return None
        
        # Calculate stop loss
        if htf_bias == "BULLISH":
            stop_loss = recent_sweep.get('price', best_zone[0]) - (10 * self.pip_size)
        else:
            stop_loss = recent_sweep.get('price', best_zone[1]) + (10 * self.pip_size)
        
        return Model2022(
            htf_bias=htf_bias,
            liquidity_swept="SSL" if "SSL" in sweep_type else "BSL",
            sweep_price=recent_sweep.get('price', 0),
            entry_zone_type=zone_type,
            entry_zone=best_zone,
            target=target,
            stop_loss=stop_loss,
            valid=valid
        )
    
    def detect_market_maker_model(self, ohlc: pd.DataFrame) -> Optional[MarketMakerModel]:
        """
        Detect Market Maker Buy/Sell Model.
        
        Looks for:
        1. Consolidation
        2. Sweep of one side
        3. Reaccumulation
        4. Move to opposite liquidity
        """
        if len(ohlc) < 50:
            return None
        
        # Find consolidation (low ATR period)
        ranges = ohlc['high'] - ohlc['low']
        avg_range = ranges.rolling(20).mean()
        
        # Find where range was small (consolidation)
        consolidation_idx = None
        for i in range(20, len(ohlc) - 10):
            if ranges.iloc[i] < avg_range.iloc[i] * 0.5:
                consolidation_idx = i
                break
        
        if consolidation_idx is None:
            return None
        
        # Get consolidation range
        consol_high = ohlc['high'].iloc[consolidation_idx-5:consolidation_idx+5].max()
        consol_low = ohlc['low'].iloc[consolidation_idx-5:consolidation_idx+5].min()
        
        # Look for sweep after consolidation
        post_consol = ohlc.iloc[consolidation_idx:]
        
        swept_high = post_consol['high'].max() > consol_high
        swept_low = post_consol['low'].min() < consol_low
        
        current_price = ohlc['close'].iloc[-1]
        
        if swept_low and current_price > consol_low:
            # MMBM - swept low, now moving up
            return MarketMakerModel(
                model_type="MMBM",
                phase="DISTRIBUTION" if current_price > consol_high else "REACCUMULATION",
                reversal_point=post_consol['low'].min(),
                current_price=current_price,
                target=ohlc['high'].max()  # BSL
            )
        elif swept_high and current_price < consol_high:
            # MMSM - swept high, now moving down
            return MarketMakerModel(
                model_type="MMSM",
                phase="DISTRIBUTION" if current_price < consol_low else "REACCUMULATION",
                reversal_point=post_consol['high'].max(),
                current_price=current_price,
                target=ohlc['low'].min()  # SSL
            )
        
        return None

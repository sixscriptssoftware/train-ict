"""
ICT Market Maker Model (MMBM / MMSM) Detector

Based on the visual guides showing the complete Market Maker model structure:

MARKET MAKER BUY MODEL (MMBM):
═══════════════════════════════════════════════════════════════════════════
    ┌──────────────────┐
    │ ORIGINAL         │ ← Target (SSL here = final TP)
    │ CONSOLIDATION    │ ← Where smart money originally accumulated
    └──────────────────┘
              │
              ▼ Sellside Curve / Markdown
        ╱╲   
       ╱  ╲  ← -1 (first lower high = engineered liquidity)
      ╱    ╲
     ╱      ╲╱╲
    ╱          ╲  ← -2 (second lower high)
   ╱            ╲
  ╱              ╲╱╲
                    ╲  ← -3 (third lower high)  
                     ╲
    ════════════════════════════════════════════ PD Array (Discount Zone)
                      │
                      ▼ MSS (breaks -3 or -2)
                     ╱╲
                    ╱  ╲ ← FVG forms here
                   ╱    ╲
                  ↑      
            SMART MONEY REVERSAL
            (Entry on FVG retracement)

PHASES:
1. Original Consolidation - Initial accumulation range (becomes target)
2. Sellside Curve - Engineered lower highs (-1, -2, -3...) creating liquidity  
3. PD Array - Discount zone where reversal occurs
4. MSS - Market Structure Shift (break of a lower high)
5. Smart Money Reversal - FVG entry targeting original consolidation

The -1, -2, -3 labels represent engineered liquidity levels above each lower high.
Each becomes an intermediate target as price reverses.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
from datetime import datetime
import pandas as pd
import numpy as np


class MarketMakerModelType(Enum):
    """Type of Market Maker Model"""
    BUY_MODEL = "mmbm"    # MMBM - Reversal from discount to premium
    SELL_MODEL = "mmsm"   # MMSM - Reversal from premium to discount


class MMModelPhase(Enum):
    """Current phase of the Market Maker Model"""
    CONSOLIDATION = "consolidation"        # Phase 1: Original range
    SELLSIDE_CURVE = "sellside_curve"      # Phase 2a: MMBM - Markdown with lower highs
    BUYSIDE_CURVE = "buyside_curve"        # Phase 2b: MMSM - Markup with higher lows
    PD_ARRAY = "pd_array"                  # Phase 3: At discount/premium zone
    MSS_PENDING = "mss_pending"            # Waiting for structure shift
    MSS_CONFIRMED = "mss_confirmed"        # Phase 4: Structure has shifted
    SMART_MONEY_REVERSAL = "smart_money_reversal"  # Phase 5: FVG/entry available
    TARGETING = "targeting"                # Active, moving toward target
    COMPLETED = "completed"                # Target reached


@dataclass 
class EngineeredLiquidity:
    """Represents an engineered liquidity level (-1, -2, -3, etc.)"""
    level_number: int  # -1, -2, -3 for MMBM; +1, +2, +3 for MMSM
    price: float
    candle_idx: int
    timestamp: datetime
    is_target: bool = False  # Whether this is the next target
    is_reached: bool = False


@dataclass
class ConsolidationRange:
    """The original consolidation range"""
    high: float
    low: float
    start_idx: int
    end_idx: int
    candle_count: int
    
    @property
    def range_size(self) -> float:
        return self.high - self.low
    
    @property 
    def midpoint(self) -> float:
        return (self.high + self.low) / 2


@dataclass
class MarketMakerSetup:
    """Complete Market Maker Model setup"""
    type: MarketMakerModelType
    phase: MMModelPhase
    
    # Original consolidation
    consolidation: Optional[ConsolidationRange] = None
    
    # Engineered liquidity levels
    engineered_levels: List[EngineeredLiquidity] = field(default_factory=list)
    
    # PD Array zone
    pd_array_high: Optional[float] = None
    pd_array_low: Optional[float] = None
    
    # MSS confirmation
    mss_level: Optional[float] = None
    mss_candle_idx: Optional[int] = None
    
    # Entry zone (FVG or OB)
    entry_zone_high: Optional[float] = None
    entry_zone_low: Optional[float] = None
    entry_type: Optional[str] = None  # 'FVG' or 'OB'
    
    # Trade levels
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None  # Original consolidation high/low
    intermediate_targets: List[float] = field(default_factory=list)  # Each -1, -2, etc.
    
    # Metadata
    confidence: float = 0.0
    symbol: str = ""
    timeframe: str = ""
    timestamp: Optional[datetime] = None
    
    @property
    def risk_reward(self) -> Optional[float]:
        if all([self.entry_price, self.stop_loss, self.take_profit]):
            risk = abs(self.entry_price - self.stop_loss)
            reward = abs(self.take_profit - self.entry_price)
            return reward / risk if risk > 0 else None
        return None
    
    @property
    def legs_count(self) -> int:
        """Number of engineered liquidity legs"""
        return len(self.engineered_levels)


class MarketMakerModelDetector:
    """
    Detects ICT Market Maker Buy/Sell Models.
    
    The detector identifies:
    1. Original consolidation ranges
    2. Engineered liquidity levels (the -1, -2, -3 lower highs or +1, +2, +3 higher lows)
    3. PD Array zones
    4. MSS confirmation
    5. Entry zones (FVG/OB)
    """
    
    def __init__(
        self,
        consolidation_min_candles: int = 10,
        consolidation_max_atr_mult: float = 1.5,
        min_engineered_levels: int = 2,
        swing_lookback: int = 5,
        pip_value: float = 0.0001
    ):
        self.consolidation_min_candles = consolidation_min_candles
        self.consolidation_max_atr_mult = consolidation_max_atr_mult
        self.min_engineered_levels = min_engineered_levels
        self.swing_lookback = swing_lookback
        self.pip_value = pip_value
        
        self.active_setups: List[MarketMakerSetup] = []
    
    def detect_consolidation(self, df: pd.DataFrame, end_idx: int) -> Optional[ConsolidationRange]:
        """
        Detect original consolidation range looking backward from end_idx.
        
        Consolidation criteria:
        - Price stays within a tight range (low ATR relative to recent average)
        - Multiple touches of highs and lows
        - Minimum number of candles
        """
        if end_idx < self.consolidation_min_candles:
            return None
        
        # Calculate ATR for reference
        atr = self._calculate_atr(df, 14)
        if atr is None or end_idx >= len(atr):
            return None
        
        avg_atr = atr[max(0, end_idx-50):end_idx].mean()
        max_range = avg_atr * self.consolidation_max_atr_mult * 10  # Convert to price range
        
        # Look backward for consolidation
        for lookback in range(self.consolidation_min_candles, min(100, end_idx)):
            start = end_idx - lookback
            window = df.iloc[start:end_idx]
            
            high = window['high'].max()
            low = window['low'].min()
            range_size = high - low
            
            # Check if range is tight enough
            if range_size <= max_range:
                # Check for multiple touches (at least 2 each)
                upper_touches = sum(window['high'] >= high * 0.998)
                lower_touches = sum(window['low'] <= low * 1.002)
                
                if upper_touches >= 2 and lower_touches >= 2:
                    return ConsolidationRange(
                        high=high,
                        low=low,
                        start_idx=start,
                        end_idx=end_idx,
                        candle_count=lookback
                    )
        
        return None
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """Calculate Average True Range"""
        if len(df) < period:
            return None
        
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def detect_engineered_liquidity(
        self, 
        df: pd.DataFrame, 
        start_idx: int, 
        model_type: MarketMakerModelType
    ) -> List[EngineeredLiquidity]:
        """
        Detect engineered liquidity levels (the -1, -2, -3 or +1, +2, +3 levels).
        
        For MMBM: Look for lower highs (each is a -N level)
        For MMSM: Look for higher lows (each is a +N level)
        """
        levels = []
        
        if model_type == MarketMakerModelType.BUY_MODEL:
            # Find lower highs (each swing high that's lower than previous)
            prev_high = df['high'].iloc[start_idx]
            level_num = 0
            
            for i in range(start_idx + self.swing_lookback, len(df)):
                # Check if this is a swing high
                is_swing = True
                for j in range(1, min(self.swing_lookback + 1, len(df) - i)):
                    if df['high'].iloc[i] < df['high'].iloc[i-j] or \
                       (i + j < len(df) and df['high'].iloc[i] < df['high'].iloc[i+j]):
                        is_swing = False
                        break
                
                if is_swing and df['high'].iloc[i] < prev_high:
                    level_num -= 1  # -1, -2, -3...
                    levels.append(EngineeredLiquidity(
                        level_number=level_num,
                        price=df['high'].iloc[i],
                        candle_idx=i,
                        timestamp=df.index[i]
                    ))
                    prev_high = df['high'].iloc[i]
        
        else:  # SELL_MODEL
            # Find higher lows (each swing low that's higher than previous)
            prev_low = df['low'].iloc[start_idx]
            level_num = 0
            
            for i in range(start_idx + self.swing_lookback, len(df)):
                # Check if this is a swing low
                is_swing = True
                for j in range(1, min(self.swing_lookback + 1, len(df) - i)):
                    if df['low'].iloc[i] > df['low'].iloc[i-j] or \
                       (i + j < len(df) and df['low'].iloc[i] > df['low'].iloc[i+j]):
                        is_swing = False
                        break
                
                if is_swing and df['low'].iloc[i] > prev_low:
                    level_num += 1  # +1, +2, +3...
                    levels.append(EngineeredLiquidity(
                        level_number=level_num,
                        price=df['low'].iloc[i],
                        candle_idx=i,
                        timestamp=df.index[i]
                    ))
                    prev_low = df['low'].iloc[i]
        
        return levels
    
    def detect_pd_array(
        self, 
        df: pd.DataFrame, 
        consolidation: ConsolidationRange,
        model_type: MarketMakerModelType
    ) -> Optional[Tuple[float, float]]:
        """
        Detect the PD Array zone (discount for MMBM, premium for MMSM).
        
        Uses higher timeframe structure or Fibonacci levels from consolidation.
        """
        if model_type == MarketMakerModelType.BUY_MODEL:
            # Discount zone = below consolidation low
            # Typically the 0.618-0.786 retracement or lower
            range_size = consolidation.range_size
            pd_high = consolidation.low
            pd_low = consolidation.low - (range_size * 0.5)  # Extend below
            return (pd_high, pd_low)
        
        else:  # SELL_MODEL
            # Premium zone = above consolidation high
            range_size = consolidation.range_size
            pd_low = consolidation.high
            pd_high = consolidation.high + (range_size * 0.5)  # Extend above
            return (pd_high, pd_low)
    
    def detect_mss(
        self, 
        df: pd.DataFrame, 
        engineered_levels: List[EngineeredLiquidity],
        model_type: MarketMakerModelType
    ) -> Optional[Tuple[float, int]]:
        """
        Detect Market Structure Shift.
        
        For MMBM: Price breaks above a lower high (one of the -N levels)
        For MMSM: Price breaks below a higher low (one of the +N levels)
        """
        if not engineered_levels:
            return None
        
        # Use the most recent engineered level as MSS reference
        last_level = engineered_levels[-1]
        
        if model_type == MarketMakerModelType.BUY_MODEL:
            # Look for break above the last lower high
            for i in range(last_level.candle_idx + 1, len(df)):
                if df['close'].iloc[i] > last_level.price:
                    return (last_level.price, i)
        
        else:  # SELL_MODEL
            # Look for break below the last higher low
            for i in range(last_level.candle_idx + 1, len(df)):
                if df['close'].iloc[i] < last_level.price:
                    return (last_level.price, i)
        
        return None
    
    def find_entry_zone(
        self, 
        df: pd.DataFrame, 
        mss_idx: int, 
        model_type: MarketMakerModelType
    ) -> Optional[Dict]:
        """
        Find FVG or OB entry zone following MSS.
        """
        lookback = min(5, mss_idx)
        
        if model_type == MarketMakerModelType.BUY_MODEL:
            # Look for bullish FVG
            for i in range(mss_idx, max(0, mss_idx - lookback), -1):
                if i < 2:
                    continue
                
                # Bullish FVG: gap between candle[i-2] high and candle[i] low
                if df['low'].iloc[i] > df['high'].iloc[i-2]:
                    return {
                        'type': 'FVG',
                        'high': df['low'].iloc[i],
                        'low': df['high'].iloc[i-2],
                        'index': i
                    }
                
                # Bullish OB: last down candle before up move
                if df['close'].iloc[i-1] < df['open'].iloc[i-1] and \
                   df['close'].iloc[i] > df['open'].iloc[i]:
                    return {
                        'type': 'OB',
                        'high': df['high'].iloc[i-1],
                        'low': df['low'].iloc[i-1],
                        'index': i-1
                    }
        
        else:  # SELL_MODEL
            # Look for bearish FVG
            for i in range(mss_idx, max(0, mss_idx - lookback), -1):
                if i < 2:
                    continue
                
                # Bearish FVG
                if df['high'].iloc[i] < df['low'].iloc[i-2]:
                    return {
                        'type': 'FVG',
                        'high': df['low'].iloc[i-2],
                        'low': df['high'].iloc[i],
                        'index': i
                    }
                
                # Bearish OB
                if df['close'].iloc[i-1] > df['open'].iloc[i-1] and \
                   df['close'].iloc[i] < df['open'].iloc[i]:
                    return {
                        'type': 'OB',
                        'high': df['high'].iloc[i-1],
                        'low': df['low'].iloc[i-1],
                        'index': i-1
                    }
        
        return None
    
    def calculate_trade_levels(
        self, 
        setup: MarketMakerSetup,
        df: pd.DataFrame,
        lowest_price: float,
        highest_price: float
    ) -> MarketMakerSetup:
        """
        Calculate entry, stop, and target levels.
        
        For MMBM:
        - Entry: FVG/OB midpoint
        - Stop: Below the lowest point of the curve
        - Targets: Each -N level, then consolidation high
        
        For MMSM:
        - Entry: FVG/OB midpoint  
        - Stop: Above the highest point of the curve
        - Targets: Each +N level, then consolidation low
        """
        if setup.entry_zone_high is None:
            return setup
        
        # Entry at zone midpoint
        setup.entry_price = (setup.entry_zone_high + setup.entry_zone_low) / 2
        
        if setup.type == MarketMakerModelType.BUY_MODEL:
            # Stop below curve low with buffer
            buffer = 5 * self.pip_value
            setup.stop_loss = lowest_price - buffer
            
            # Final target is consolidation high
            if setup.consolidation:
                setup.take_profit = setup.consolidation.high
            
            # Intermediate targets are each engineered level (in reverse order)
            for level in sorted(setup.engineered_levels, key=lambda x: x.level_number, reverse=True):
                if level.price > setup.entry_price:
                    setup.intermediate_targets.append(level.price)
        
        else:  # SELL_MODEL
            # Stop above curve high with buffer
            buffer = 5 * self.pip_value
            setup.stop_loss = highest_price + buffer
            
            # Final target is consolidation low
            if setup.consolidation:
                setup.take_profit = setup.consolidation.low
            
            # Intermediate targets
            for level in sorted(setup.engineered_levels, key=lambda x: x.level_number):
                if level.price < setup.entry_price:
                    setup.intermediate_targets.append(level.price)
        
        return setup
    
    def analyze(
        self, 
        df: pd.DataFrame, 
        symbol: str = "", 
        timeframe: str = ""
    ) -> List[MarketMakerSetup]:
        """
        Main analysis - scan for Market Maker Buy/Sell Models.
        """
        if len(df) < 50:
            return []
        
        setups = []
        
        # Scan for potential consolidation breakouts
        for scan_end in range(50, len(df) - 20):
            # Try to find consolidation
            consolidation = self.detect_consolidation(df, scan_end)
            
            if consolidation is None:
                continue
            
            # Determine model type based on breakout direction
            next_candles = df.iloc[scan_end:min(scan_end + 10, len(df))]
            
            if len(next_candles) < 5:
                continue
            
            broke_down = next_candles['low'].min() < consolidation.low
            broke_up = next_candles['high'].max() > consolidation.high
            
            if broke_down and not broke_up:
                model_type = MarketMakerModelType.BUY_MODEL
            elif broke_up and not broke_down:
                model_type = MarketMakerModelType.SELL_MODEL
            else:
                continue  # No clear direction
            
            # Detect engineered liquidity levels
            engineered = self.detect_engineered_liquidity(df, scan_end, model_type)
            
            if len(engineered) < self.min_engineered_levels:
                continue
            
            # Detect PD Array
            pd_array = self.detect_pd_array(df, consolidation, model_type)
            
            # Detect MSS
            mss_result = self.detect_mss(df, engineered, model_type)
            
            if mss_result is None:
                # Model still developing - might be in curve phase
                phase = MMModelPhase.SELLSIDE_CURVE if model_type == MarketMakerModelType.BUY_MODEL \
                        else MMModelPhase.BUYSIDE_CURVE
            else:
                phase = MMModelPhase.MSS_CONFIRMED
            
            # Create setup
            setup = MarketMakerSetup(
                type=model_type,
                phase=phase,
                consolidation=consolidation,
                engineered_levels=engineered,
                pd_array_high=pd_array[0] if pd_array else None,
                pd_array_low=pd_array[1] if pd_array else None,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=df.index[-1]
            )
            
            if mss_result:
                setup.mss_level, setup.mss_candle_idx = mss_result
                
                # Find entry zone
                entry_zone = self.find_entry_zone(df, setup.mss_candle_idx, model_type)
                
                if entry_zone:
                    setup.entry_zone_high = entry_zone['high']
                    setup.entry_zone_low = entry_zone['low']
                    setup.entry_type = entry_zone['type']
                    setup.phase = MMModelPhase.SMART_MONEY_REVERSAL
                    
                    # Calculate levels
                    curve_section = df.iloc[scan_end:]
                    lowest = curve_section['low'].min()
                    highest = curve_section['high'].max()
                    setup = self.calculate_trade_levels(setup, df, lowest, highest)
            
            # Calculate confidence
            setup.confidence = self._calculate_confidence(setup)
            
            if setup.confidence >= 0.5:
                setups.append(setup)
        
        # Keep only the most recent/best setup per type
        self.active_setups = self._deduplicate_setups(setups)
        return self.active_setups
    
    def _calculate_confidence(self, setup: MarketMakerSetup) -> float:
        """Calculate confidence score"""
        confidence = 0.3  # Base
        
        # Consolidation quality
        if setup.consolidation and setup.consolidation.candle_count >= 15:
            confidence += 0.15
        
        # Number of engineered levels (more = better)
        if len(setup.engineered_levels) >= 3:
            confidence += 0.15
        elif len(setup.engineered_levels) >= 2:
            confidence += 0.10
        
        # MSS confirmed
        if setup.mss_level:
            confidence += 0.15
        
        # Entry zone found
        if setup.entry_type:
            confidence += 0.10
            if setup.entry_type == 'FVG':
                confidence += 0.05
        
        # Good R:R
        if setup.risk_reward and setup.risk_reward >= 3:
            confidence += 0.10
        
        return min(confidence, 1.0)
    
    def _deduplicate_setups(self, setups: List[MarketMakerSetup]) -> List[MarketMakerSetup]:
        """Keep only the best setup of each type"""
        best = {}
        for setup in setups:
            key = setup.type.value
            if key not in best or setup.confidence > best[key].confidence:
                best[key] = setup
        return list(best.values())
    
    def format_setup(self, setup: MarketMakerSetup) -> str:
        """Format setup for display"""
        model_name = "MARKET MAKER BUY MODEL" if setup.type == MarketMakerModelType.BUY_MODEL \
                     else "MARKET MAKER SELL MODEL"
        direction = "🟢 LONG" if setup.type == MarketMakerModelType.BUY_MODEL else "🔴 SHORT"
        
        lines = [
            f"═══ {model_name} ═══",
            f"Direction: {direction}",
            f"Phase: {setup.phase.value.replace('_', ' ').title()}",
        ]
        
        if setup.consolidation:
            lines.append(f"Original Consolidation: {setup.consolidation.low:.5f} - {setup.consolidation.high:.5f}")
        
        if setup.engineered_levels:
            levels_str = ", ".join([f"{l.level_number}@{l.price:.5f}" for l in setup.engineered_levels])
            lines.append(f"Engineered Levels: {levels_str}")
        
        if setup.mss_level:
            lines.append(f"MSS Confirmed @ {setup.mss_level:.5f}")
        
        if setup.entry_type:
            lines.append(f"Entry Zone ({setup.entry_type}): {setup.entry_zone_low:.5f} - {setup.entry_zone_high:.5f}")
        
        if setup.entry_price:
            lines.extend([
                "",
                f"📍 Entry: {setup.entry_price:.5f}",
                f"🛑 Stop: {setup.stop_loss:.5f}",
                f"🎯 Target: {setup.take_profit:.5f}" if setup.take_profit else "",
            ])
            
            if setup.intermediate_targets:
                targets = ", ".join([f"{t:.5f}" for t in setup.intermediate_targets[:3]])
                lines.append(f"📊 Partials: {targets}")
            
            if setup.risk_reward:
                lines.append(f"R:R = 1:{setup.risk_reward:.1f}")
        
        lines.append(f"\nConfidence: {setup.confidence*100:.0f}%")
        
        return "\n".join(filter(None, lines))


# Convenience functions
def detect_mmbm(df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> List[MarketMakerSetup]:
    """Detect Market Maker Buy Model setups"""
    detector = MarketMakerModelDetector()
    setups = detector.analyze(df, symbol, timeframe)
    return [s for s in setups if s.type == MarketMakerModelType.BUY_MODEL]


def detect_mmsm(df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> List[MarketMakerSetup]:
    """Detect Market Maker Sell Model setups"""
    detector = MarketMakerModelDetector()
    setups = detector.analyze(df, symbol, timeframe)
    return [s for s in setups if s.type == MarketMakerModelType.SELL_MODEL]


def detect_market_maker_model(df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> List[MarketMakerSetup]:
    """Detect all Market Maker Model setups"""
    detector = MarketMakerModelDetector()
    return detector.analyze(df, symbol, timeframe)

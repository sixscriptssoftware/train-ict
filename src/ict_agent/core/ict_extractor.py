"""
ICT Data Extractor
Unified extraction of ICT concepts from raw detector output.
Returns clean, usable data structures for trading decisions.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal
from enum import Enum
import pandas as pd
import numpy as np


class Direction(Enum):
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


@dataclass
class SwingPoint:
    """A swing high or low"""
    timestamp: pd.Timestamp
    price: float
    type: Literal["HIGH", "LOW"]
    broken: bool = False


@dataclass
class StructureBreak:
    """BOS, MSS, or CHoCH"""
    timestamp: pd.Timestamp
    type: Literal["BOS", "MSS", "CHOCH"]
    direction: Direction
    price: float
    has_displacement: bool


@dataclass
class FairValueGap:
    """An imbalance in price"""
    timestamp: pd.Timestamp
    direction: Direction
    top: float
    bottom: float
    ce: float  # Consequent Encroachment (midpoint)
    mitigated: bool
    
    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass
class OrderBlock:
    """Institutional footprint"""
    timestamp: pd.Timestamp
    direction: Direction
    top: float
    bottom: float
    mitigated: bool
    
    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass
class LiquidityLevel:
    """BSL or SSL"""
    price: float
    type: Literal["BSL", "SSL"]  # Buy-side or Sell-side
    strength: float
    is_equal_level: bool  # Equal highs/lows
    swept: bool


@dataclass
class LiquiditySweep:
    """Stop hunt event"""
    timestamp: pd.Timestamp
    type: Literal["BSL", "SSL"]
    price: float


@dataclass
class ICTContext:
    """Complete ICT analysis context"""
    # Current state
    current_price: float
    trend: Direction
    
    # Structure
    swing_highs: List[SwingPoint] = field(default_factory=list)
    swing_lows: List[SwingPoint] = field(default_factory=list)
    structure_breaks: List[StructureBreak] = field(default_factory=list)
    
    # PD Arrays (Premium/Discount zones)
    fvgs: List[FairValueGap] = field(default_factory=list)
    order_blocks: List[OrderBlock] = field(default_factory=list)
    
    # Liquidity
    bsl_levels: List[LiquidityLevel] = field(default_factory=list)
    ssl_levels: List[LiquidityLevel] = field(default_factory=list)
    sweeps: List[LiquiditySweep] = field(default_factory=list)
    
    # Computed
    @property
    def open_fvgs(self) -> List[FairValueGap]:
        return [f for f in self.fvgs if not f.mitigated]
    
    @property
    def fresh_obs(self) -> List[OrderBlock]:
        return [o for o in self.order_blocks if not o.mitigated]
    
    @property
    def bearish_pd_arrays(self) -> List:
        """FVGs and OBs for short entries"""
        return [f for f in self.open_fvgs if f.direction == Direction.BEARISH] + \
               [o for o in self.fresh_obs if o.direction == Direction.BEARISH]
    
    @property
    def bullish_pd_arrays(self) -> List:
        """FVGs and OBs for long entries"""
        return [f for f in self.open_fvgs if f.direction == Direction.BULLISH] + \
               [o for o in self.fresh_obs if o.direction == Direction.BULLISH]
    
    @property
    def nearest_bsl(self) -> Optional[float]:
        """Nearest buy-side liquidity above price"""
        above = [l.price for l in self.bsl_levels if l.price > self.current_price and not l.swept]
        return min(above) if above else None
    
    @property
    def nearest_ssl(self) -> Optional[float]:
        """Nearest sell-side liquidity below price"""
        below = [l.price for l in self.ssl_levels if l.price < self.current_price and not l.swept]
        return max(below) if below else None
    
    @property
    def last_sweep(self) -> Optional[LiquiditySweep]:
        return self.sweeps[-1] if self.sweeps else None
    
    def price_in_pd_array(self) -> Optional[dict]:
        """Check if price is currently in any PD array"""
        for fvg in self.open_fvgs:
            if fvg.contains_price(self.current_price):
                return {"type": "FVG", "direction": fvg.direction, "zone": fvg}
        for ob in self.fresh_obs:
            if ob.contains_price(self.current_price):
                return {"type": "OB", "direction": ob.direction, "zone": ob}
        return None


class ICTExtractor:
    """
    Extracts clean ICT data from detector outputs.
    
    Usage:
        from ict_agent.core.ict_extractor import ICTExtractor
        from ict_agent.detectors.market_structure import MarketStructureAnalyzer
        from ict_agent.detectors.fvg import FVGDetector
        from ict_agent.detectors.order_block import OrderBlockDetector
        from ict_agent.detectors.liquidity import LiquidityDetector
        
        extractor = ICTExtractor()
        context = extractor.extract(df)
        
        print(f"Trend: {context.trend}")
        print(f"Open FVGs: {len(context.open_fvgs)}")
        print(f"Draw on liquidity: {context.nearest_ssl}")
    """
    
    def __init__(
        self,
        swing_length: int = 5,
        min_fvg_pips: float = 2,
        pip_size: float = 0.0001
    ):
        self.swing_length = swing_length
        self.min_fvg_pips = min_fvg_pips
        self.pip_size = pip_size
    
    def extract(self, ohlc: pd.DataFrame) -> ICTContext:
        """Extract all ICT concepts from OHLC data"""
        from ict_agent.detectors.market_structure import MarketStructureAnalyzer
        from ict_agent.detectors.fvg import FVGDetector
        from ict_agent.detectors.order_block import OrderBlockDetector
        from ict_agent.detectors.liquidity import LiquidityDetector
        
        current_price = ohlc['close'].iloc[-1]
        
        # Market Structure
        msa = MarketStructureAnalyzer(swing_length=self.swing_length)
        ms_result = msa.analyze(ohlc)
        
        trend_val = ms_result['structure_trend'].iloc[-1]
        trend = Direction.BULLISH if trend_val > 0 else Direction.BEARISH if trend_val < 0 else Direction.NEUTRAL
        
        # Extract swings
        swing_highs = []
        swing_lows = []
        swings = ms_result[ms_result['swing_type'] != 0]
        for idx, row in swings.iterrows():
            if row['swing_type'] == 1:
                swing_highs.append(SwingPoint(
                    timestamp=idx,
                    price=row['swing_level'],
                    type="HIGH"
                ))
            else:
                swing_lows.append(SwingPoint(
                    timestamp=idx,
                    price=row['swing_level'],
                    type="LOW"
                ))
        
        # Extract structure breaks
        structure_breaks = []
        breaks = ms_result[ms_result['break_type'] != '']
        for idx, row in breaks.iterrows():
            direction = Direction.BULLISH if row['break_direction'] > 0 else Direction.BEARISH
            structure_breaks.append(StructureBreak(
                timestamp=idx,
                type=row['break_type'].upper(),
                direction=direction,
                price=ohlc.loc[idx, 'close'],
                has_displacement=row['has_displacement']
            ))
        
        # FVGs
        fvg_detector = FVGDetector(min_gap_pips=self.min_fvg_pips, pip_size=self.pip_size)
        fvg_result = fvg_detector.detect(ohlc)
        
        fvgs = []
        fvg_rows = fvg_result[fvg_result['fvg_top'].notna()]
        for idx, row in fvg_rows.iterrows():
            direction = Direction.BULLISH if row['fvg_direction'] > 0 else Direction.BEARISH
            fvgs.append(FairValueGap(
                timestamp=idx,
                direction=direction,
                top=row['fvg_top'],
                bottom=row['fvg_bottom'],
                ce=row['fvg_midpoint'],
                mitigated=bool(row['fvg_mitigated'])
            ))
        
        # Order Blocks
        ob_detector = OrderBlockDetector(pip_size=self.pip_size)
        ob_result = ob_detector.detect(ohlc)
        
        order_blocks = []
        ob_rows = ob_result[ob_result['ob_top'].notna()]
        for idx, row in ob_rows.iterrows():
            direction = Direction.BULLISH if row['ob_direction'] > 0 else Direction.BEARISH
            order_blocks.append(OrderBlock(
                timestamp=idx,
                direction=direction,
                top=row['ob_top'],
                bottom=row['ob_bottom'],
                mitigated=bool(row['ob_mitigated'])
            ))
        
        # Liquidity
        liq_detector = LiquidityDetector()
        liq_result = liq_detector.detect(ohlc)
        
        bsl_levels = []
        ssl_levels = []
        sweeps = []
        
        liq_rows = liq_result[liq_result['liquidity_level'].notna()]
        for idx, row in liq_rows.iterrows():
            if pd.isna(row['liquidity_level']):
                continue
            level = LiquidityLevel(
                price=row['liquidity_level'],
                type="BSL" if row['liquidity_type'] == 1 else "SSL",
                strength=row['liquidity_strength'],
                is_equal_level=bool(row['is_equal_level']),
                swept=bool(row['is_sweep'])
            )
            if row['liquidity_type'] == 1:
                bsl_levels.append(level)
            else:
                ssl_levels.append(level)
        
        # Sweeps
        sweep_rows = liq_result[liq_result['is_sweep'] == True]
        for idx, row in sweep_rows.iterrows():
            if pd.notna(row['liquidity_level']):
                sweeps.append(LiquiditySweep(
                    timestamp=idx,
                    type="BSL" if row['sweep_type'] > 0 else "SSL",
                    price=row['liquidity_level']
                ))
        
        return ICTContext(
            current_price=current_price,
            trend=trend,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            structure_breaks=structure_breaks,
            fvgs=fvgs,
            order_blocks=order_blocks,
            bsl_levels=bsl_levels,
            ssl_levels=ssl_levels,
            sweeps=sweeps
        )
    
    def format_analysis(self, context: ICTContext, pair: str = "EUR/USD") -> str:
        """Format ICT context as readable analysis"""
        lines = []
        lines.append("=" * 70)
        lines.append(f"  ICT ANALYSIS: {pair} @ {context.current_price:.5f}")
        lines.append("=" * 70)
        
        # Trend
        trend_emoji = "🟢" if context.trend == Direction.BULLISH else "🔴" if context.trend == Direction.BEARISH else "⚪"
        lines.append(f"\n📐 MARKET STRUCTURE: {trend_emoji} {context.trend.name}")
        
        # Recent structure break
        if context.structure_breaks:
            last_break = context.structure_breaks[-1]
            lines.append(f"  Last Break: {last_break.type} {last_break.direction.name} @ {last_break.timestamp.strftime('%m-%d %H:%M')}")
        
        # Swings
        if context.swing_highs:
            last_sh = context.swing_highs[-1]
            lines.append(f"  Last Swing High: {last_sh.price:.5f}")
        if context.swing_lows:
            last_sl = context.swing_lows[-1]
            lines.append(f"  Last Swing Low: {last_sl.price:.5f}")
        
        # PD Arrays
        lines.append(f"\n📊 PD ARRAYS")
        
        # FVGs
        open_fvgs = context.open_fvgs
        if open_fvgs:
            lines.append(f"  Open FVGs ({len(open_fvgs)}):")
            for fvg in open_fvgs[-3:]:
                direction = "BULL" if fvg.direction == Direction.BULLISH else "BEAR"
                in_zone = "🎯 PRICE HERE" if fvg.contains_price(context.current_price) else ""
                lines.append(f"    {direction} FVG: {fvg.bottom:.5f} - {fvg.top:.5f} (CE: {fvg.ce:.5f}) {in_zone}")
        else:
            lines.append("  No open FVGs")
        
        # OBs
        fresh_obs = context.fresh_obs
        if fresh_obs:
            lines.append(f"  Fresh OBs ({len(fresh_obs)}):")
            for ob in fresh_obs[-3:]:
                direction = "BULL" if ob.direction == Direction.BULLISH else "BEAR"
                in_zone = "🎯 PRICE HERE" if ob.contains_price(context.current_price) else ""
                lines.append(f"    {direction} OB: {ob.bottom:.5f} - {ob.top:.5f} {in_zone}")
        else:
            lines.append("  No fresh OBs")
        
        # Liquidity
        lines.append(f"\n💧 LIQUIDITY")
        lines.append(f"  BSL (stops above): {context.nearest_bsl:.5f}" if context.nearest_bsl else "  BSL: None nearby")
        lines.append(f"  SSL (stops below): {context.nearest_ssl:.5f}" if context.nearest_ssl else "  SSL: None nearby")
        
        # Sweeps
        if context.sweeps:
            lines.append(f"\n🔥 RECENT SWEEPS:")
            for sweep in context.sweeps[-3:]:
                lines.append(f"    {sweep.timestamp.strftime('%m-%d %H:%M')} - {sweep.type} @ {sweep.price:.5f}")
        
        # Trade Setup Summary
        lines.append(f"\n🎯 SETUP SUMMARY:")
        if context.trend == Direction.BEARISH:
            lines.append("  Looking SHORT - IRL to ERL")
            lines.append(f"  Entry Zone: Bearish FVG/OB above")
            lines.append(f"  Target: SSL @ {context.nearest_ssl:.5f}" if context.nearest_ssl else "  Target: Next SSL")
        elif context.trend == Direction.BULLISH:
            lines.append("  Looking LONG - IRL to ERL")
            lines.append(f"  Entry Zone: Bullish FVG/OB below")
            lines.append(f"  Target: BSL @ {context.nearest_bsl:.5f}" if context.nearest_bsl else "  Target: Next BSL")
        else:
            lines.append("  NEUTRAL - Wait for structure break")
        
        lines.append("=" * 70)
        return "\n".join(lines)

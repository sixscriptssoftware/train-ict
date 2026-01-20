"""
ICT Turtle Soup Pattern Detector

Turtle Soup exploits FAILED breakouts - the opposite of traditional breakout trading.
When retail traders place stops above/below swing points, institutions sweep that 
liquidity before reversing. This detector identifies those reversal setups.

TURTLE SOUP BUY (Bullish):
1. Price sweeps below a significant swing low (triggers sell stops = BSL sweep)
2. Price fails to continue lower (failed breakdown)
3. MSS confirms reversal (breaks previous lower high)
4. Entry on FVG or OB retracement
5. Target: Next BSL above (swing high)

TURTLE SOUP SELL (Bearish):
1. Price sweeps above a significant swing high (triggers buy stops = SSL sweep)
2. Price fails to continue higher (failed breakout)
3. MSS confirms reversal (breaks previous higher low)
4. Entry on FVG or OB retracement
5. Target: Next SSL below (swing low)

Key insight: The sweep IS the manipulation - we trade the reversal.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
from datetime import datetime
import pandas as pd


class TurtleSoupType(Enum):
    """Type of Turtle Soup setup"""
    BULLISH = "bullish"   # Sweep low, reverse up
    BEARISH = "bearish"   # Sweep high, reverse down


class SweepStatus(Enum):
    """Status of the liquidity sweep"""
    PENDING = "pending"           # Watching for sweep
    SWEPT = "swept"               # Liquidity has been swept
    CONFIRMED = "confirmed"       # MSS confirmed the reversal
    ENTRY_READY = "entry_ready"   # FVG/OB available for entry
    ACTIVE = "active"             # Trade is active
    INVALIDATED = "invalidated"   # Setup failed


@dataclass
class LiquidityLevel:
    """Represents a liquidity pool (SSL or BSL)"""
    price: float
    timestamp: datetime
    type: str  # 'SSL' (above swing high) or 'BSL' (below swing low)
    strength: int  # Number of times this level has been tested
    swept: bool = False
    sweep_time: Optional[datetime] = None
    
    def __repr__(self):
        return f"{self.type}@{self.price:.5f} ({'SWEPT' if self.swept else 'ACTIVE'})"


@dataclass
class TurtleSoupSetup:
    """Complete Turtle Soup trading setup"""
    type: TurtleSoupType
    status: SweepStatus
    
    # Liquidity info
    swept_level: LiquidityLevel
    sweep_candle_idx: int
    sweep_low: float  # For bullish - the actual sweep low
    sweep_high: float  # For bearish - the actual sweep high
    
    # MSS confirmation
    mss_confirmed: bool = False
    mss_level: Optional[float] = None
    mss_candle_idx: Optional[int] = None
    
    # Entry zone
    entry_zone_high: Optional[float] = None
    entry_zone_low: Optional[float] = None
    entry_type: Optional[str] = None  # 'FVG' or 'OB'
    
    # Trade levels
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Metadata
    confidence: float = 0.0
    timeframe: str = ""
    symbol: str = ""
    timestamp: Optional[datetime] = None
    
    @property
    def risk_reward(self) -> Optional[float]:
        """Calculate risk-reward ratio"""
        if all([self.entry_price, self.stop_loss, self.take_profit]):
            risk = abs(self.entry_price - self.stop_loss)
            reward = abs(self.take_profit - self.entry_price)
            return reward / risk if risk > 0 else None
        return None


class TurtleSoupDetector:
    """
    Detects ICT Turtle Soup patterns - failed breakouts following liquidity sweeps.
    
    The detector:
    1. Identifies significant liquidity levels (swing highs/lows)
    2. Monitors for sweeps beyond those levels
    3. Confirms reversal via Market Structure Shift
    4. Identifies entry zones (FVG or OB)
    """
    
    def __init__(
        self,
        swing_lookback: int = 20,
        sweep_threshold_pips: float = 3.0,
        min_sweep_rejection: float = 0.5,  # Minimum rejection as % of sweep candle
        mss_lookback: int = 10,
        pip_value: float = 0.0001
    ):
        self.swing_lookback = swing_lookback
        self.sweep_threshold_pips = sweep_threshold_pips
        self.min_sweep_rejection = min_sweep_rejection
        self.mss_lookback = mss_lookback
        self.pip_value = pip_value
        
        # State
        self.liquidity_levels: List[LiquidityLevel] = []
        self.active_setups: List[TurtleSoupSetup] = []
        self.completed_setups: List[TurtleSoupSetup] = []
        
    def identify_swing_points(self, df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        """
        Identify swing highs and swing lows in price data.
        
        Returns:
            Tuple of (swing_highs, swing_lows) with price and index info
        """
        swing_highs = []
        swing_lows = []
        
        lookback = min(self.swing_lookback, len(df) // 3)
        
        for i in range(lookback, len(df) - lookback):
            # Check for swing high
            is_swing_high = True
            for j in range(1, lookback + 1):
                if df['high'].iloc[i] <= df['high'].iloc[i - j] or \
                   df['high'].iloc[i] <= df['high'].iloc[i + j]:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_highs.append({
                    'price': df['high'].iloc[i],
                    'index': i,
                    'timestamp': df.index[i] if hasattr(df.index[i], 'timestamp') else df.index[i]
                })
            
            # Check for swing low
            is_swing_low = True
            for j in range(1, lookback + 1):
                if df['low'].iloc[i] >= df['low'].iloc[i - j] or \
                   df['low'].iloc[i] >= df['low'].iloc[i + j]:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_lows.append({
                    'price': df['low'].iloc[i],
                    'index': i,
                    'timestamp': df.index[i] if hasattr(df.index[i], 'timestamp') else df.index[i]
                })
        
        return swing_highs, swing_lows
    
    def build_liquidity_map(self, df: pd.DataFrame) -> List[LiquidityLevel]:
        """
        Build a map of liquidity levels from swing points.
        SSL (Sellside Liquidity) = above swing highs
        BSL (Buyside Liquidity) = below swing lows
        """
        swing_highs, swing_lows = self.identify_swing_points(df)
        
        self.liquidity_levels = []
        
        # SSL levels (above swing highs where buy stops rest)
        for sh in swing_highs:
            level = LiquidityLevel(
                price=sh['price'],
                timestamp=sh['timestamp'],
                type='SSL',
                strength=1
            )
            # Check if similar level exists (cluster)
            for existing in self.liquidity_levels:
                if existing.type == 'SSL' and \
                   abs(existing.price - level.price) < self.sweep_threshold_pips * self.pip_value:
                    existing.strength += 1
                    break
            else:
                self.liquidity_levels.append(level)
        
        # BSL levels (below swing lows where sell stops rest)
        for sl in swing_lows:
            level = LiquidityLevel(
                price=sl['price'],
                timestamp=sl['timestamp'],
                type='BSL',
                strength=1
            )
            # Check if similar level exists (cluster)
            for existing in self.liquidity_levels:
                if existing.type == 'BSL' and \
                   abs(existing.price - level.price) < self.sweep_threshold_pips * self.pip_value:
                    existing.strength += 1
                    break
            else:
                self.liquidity_levels.append(level)
        
        return self.liquidity_levels
    
    def detect_sweep(self, df: pd.DataFrame, candle_idx: int) -> Optional[Tuple[LiquidityLevel, TurtleSoupType]]:
        """
        Detect if the current candle sweeps any liquidity level.
        
        A valid sweep:
        1. Price exceeds the liquidity level (triggers stops)
        2. Price closes back inside (failed breakout)
        3. Shows rejection (long wick relative to body)
        """
        if candle_idx >= len(df):
            return None
            
        candle = df.iloc[candle_idx]
        current_price = candle['close']
        
        for level in self.liquidity_levels:
            if level.swept:
                continue
                
            if level.type == 'BSL':
                # Bullish Turtle Soup: Sweep below swing low
                # Price wicks below but closes above
                if candle['low'] < level.price and candle['close'] > level.price:
                    # Check for rejection (lower wick)
                    body = abs(candle['close'] - candle['open'])
                    lower_wick = min(candle['open'], candle['close']) - candle['low']
                    total_range = candle['high'] - candle['low']
                    
                    if total_range > 0 and lower_wick / total_range >= self.min_sweep_rejection:
                        level.swept = True
                        level.sweep_time = df.index[candle_idx]
                        return (level, TurtleSoupType.BULLISH)
            
            elif level.type == 'SSL':
                # Bearish Turtle Soup: Sweep above swing high
                # Price wicks above but closes below
                if candle['high'] > level.price and candle['close'] < level.price:
                    # Check for rejection (upper wick)
                    body = abs(candle['close'] - candle['open'])
                    upper_wick = candle['high'] - max(candle['open'], candle['close'])
                    total_range = candle['high'] - candle['low']
                    
                    if total_range > 0 and upper_wick / total_range >= self.min_sweep_rejection:
                        level.swept = True
                        level.sweep_time = df.index[candle_idx]
                        return (level, TurtleSoupType.BEARISH)
        
        return None
    
    def detect_mss(self, df: pd.DataFrame, start_idx: int, soup_type: TurtleSoupType) -> Optional[Tuple[float, int]]:
        """
        Detect Market Structure Shift following the sweep.
        
        Bullish MSS: Price breaks above a previous lower high
        Bearish MSS: Price breaks below a previous higher low
        
        Returns:
            Tuple of (MSS level price, candle index of break) or None
        """
        if start_idx >= len(df):
            return None
            
        end_idx = min(start_idx + self.mss_lookback, len(df))
        
        if soup_type == TurtleSoupType.BULLISH:
            # Looking for break of a lower high (bullish MSS)
            # Find the most recent lower high before the sweep
            swing_high = None
            for i in range(start_idx - 1, max(0, start_idx - 20), -1):
                if i >= 2 and df['high'].iloc[i] > df['high'].iloc[i-1] and \
                   df['high'].iloc[i] > df['high'].iloc[i+1]:
                    swing_high = df['high'].iloc[i]
                    break
            
            if swing_high is None:
                return None
            
            # Check if price breaks above this level
            for i in range(start_idx + 1, end_idx):
                if df['close'].iloc[i] > swing_high:
                    return (swing_high, i)
        
        else:  # BEARISH
            # Looking for break of a higher low (bearish MSS)
            swing_low = None
            for i in range(start_idx - 1, max(0, start_idx - 20), -1):
                if i >= 2 and df['low'].iloc[i] < df['low'].iloc[i-1] and \
                   df['low'].iloc[i] < df['low'].iloc[i+1]:
                    swing_low = df['low'].iloc[i]
                    break
            
            if swing_low is None:
                return None
            
            # Check if price breaks below this level
            for i in range(start_idx + 1, end_idx):
                if df['close'].iloc[i] < swing_low:
                    return (swing_low, i)
        
        return None
    
    def find_entry_zone(self, df: pd.DataFrame, mss_idx: int, soup_type: TurtleSoupType) -> Optional[Dict]:
        """
        Find FVG or OB for entry following MSS confirmation.
        
        Returns entry zone details including high, low, and type.
        """
        lookback = min(5, mss_idx)
        
        if soup_type == TurtleSoupType.BULLISH:
            # Look for bullish FVG or bullish OB
            for i in range(mss_idx, mss_idx - lookback, -1):
                if i < 2:
                    continue
                    
                # Check for bullish FVG (gap between candle 1 high and candle 3 low)
                if df['low'].iloc[i] > df['high'].iloc[i-2]:
                    return {
                        'type': 'FVG',
                        'high': df['low'].iloc[i],
                        'low': df['high'].iloc[i-2],
                        'index': i
                    }
                
                # Check for bullish OB (last down candle before up move)
                if df['close'].iloc[i-1] < df['open'].iloc[i-1] and \
                   df['close'].iloc[i] > df['open'].iloc[i]:
                    return {
                        'type': 'OB',
                        'high': df['high'].iloc[i-1],
                        'low': df['low'].iloc[i-1],
                        'index': i-1
                    }
        
        else:  # BEARISH
            # Look for bearish FVG or bearish OB
            for i in range(mss_idx, mss_idx - lookback, -1):
                if i < 2:
                    continue
                    
                # Check for bearish FVG
                if df['high'].iloc[i] < df['low'].iloc[i-2]:
                    return {
                        'type': 'FVG',
                        'high': df['low'].iloc[i-2],
                        'low': df['high'].iloc[i],
                        'index': i
                    }
                
                # Check for bearish OB
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
        setup: TurtleSoupSetup, 
        df: pd.DataFrame
    ) -> TurtleSoupSetup:
        """
        Calculate entry, stop-loss, and take-profit levels for the setup.
        """
        if setup.entry_zone_high is None or setup.entry_zone_low is None:
            return setup
        
        if setup.type == TurtleSoupType.BULLISH:
            # Entry at midpoint of zone
            setup.entry_price = (setup.entry_zone_high + setup.entry_zone_low) / 2
            
            # Stop below the sweep low with buffer
            buffer = self.sweep_threshold_pips * self.pip_value
            setup.stop_loss = setup.sweep_low - buffer
            
            # Target: Next SSL (swing high) above
            for level in sorted(self.liquidity_levels, key=lambda x: x.price):
                if level.type == 'SSL' and level.price > setup.entry_price and not level.swept:
                    setup.take_profit = level.price
                    break
            
            if setup.take_profit is None:
                # Use 2:1 RR as default
                risk = setup.entry_price - setup.stop_loss
                setup.take_profit = setup.entry_price + (risk * 2)
        
        else:  # BEARISH
            # Entry at midpoint of zone
            setup.entry_price = (setup.entry_zone_high + setup.entry_zone_low) / 2
            
            # Stop above the sweep high with buffer
            buffer = self.sweep_threshold_pips * self.pip_value
            setup.stop_loss = setup.sweep_high + buffer
            
            # Target: Next BSL (swing low) below
            for level in sorted(self.liquidity_levels, key=lambda x: x.price, reverse=True):
                if level.type == 'BSL' and level.price < setup.entry_price and not level.swept:
                    setup.take_profit = level.price
                    break
            
            if setup.take_profit is None:
                # Use 2:1 RR as default
                risk = setup.stop_loss - setup.entry_price
                setup.take_profit = setup.entry_price - (risk * 2)
        
        return setup
    
    def analyze(
        self, 
        df: pd.DataFrame, 
        symbol: str = "", 
        timeframe: str = ""
    ) -> List[TurtleSoupSetup]:
        """
        Main analysis method - scans for Turtle Soup setups.
        
        Args:
            df: OHLCV DataFrame with datetime index
            symbol: Trading symbol
            timeframe: Timeframe string
            
        Returns:
            List of detected TurtleSoupSetup objects
        """
        if len(df) < self.swing_lookback * 2:
            return []
        
        # Build liquidity map
        self.build_liquidity_map(df)
        
        setups = []
        
        # Scan for sweeps in recent candles
        scan_start = max(self.swing_lookback, len(df) - 50)
        
        for i in range(scan_start, len(df)):
            sweep_result = self.detect_sweep(df, i)
            
            if sweep_result:
                level, soup_type = sweep_result
                
                # Create initial setup
                setup = TurtleSoupSetup(
                    type=soup_type,
                    status=SweepStatus.SWEPT,
                    swept_level=level,
                    sweep_candle_idx=i,
                    sweep_low=df['low'].iloc[i] if soup_type == TurtleSoupType.BULLISH else 0,
                    sweep_high=df['high'].iloc[i] if soup_type == TurtleSoupType.BEARISH else 0,
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=df.index[i] if hasattr(df.index[i], 'timestamp') else datetime.now()
                )
                
                # Check for MSS confirmation
                mss_result = self.detect_mss(df, i, soup_type)
                
                if mss_result:
                    mss_level, mss_idx = mss_result
                    setup.mss_confirmed = True
                    setup.mss_level = mss_level
                    setup.mss_candle_idx = mss_idx
                    setup.status = SweepStatus.CONFIRMED
                    
                    # Find entry zone
                    entry_zone = self.find_entry_zone(df, mss_idx, soup_type)
                    
                    if entry_zone:
                        setup.entry_zone_high = entry_zone['high']
                        setup.entry_zone_low = entry_zone['low']
                        setup.entry_type = entry_zone['type']
                        setup.status = SweepStatus.ENTRY_READY
                        
                        # Calculate trade levels
                        setup = self.calculate_trade_levels(setup, df)
                        
                        # Calculate confidence
                        setup.confidence = self._calculate_confidence(setup, df)
                
                if setup.status in [SweepStatus.CONFIRMED, SweepStatus.ENTRY_READY]:
                    setups.append(setup)
        
        self.active_setups = setups
        return setups
    
    def _calculate_confidence(self, setup: TurtleSoupSetup, df: pd.DataFrame) -> float:
        """Calculate confidence score for the setup"""
        confidence = 0.5  # Base confidence
        
        # MSS confirmed
        if setup.mss_confirmed:
            confidence += 0.15
        
        # Entry zone found
        if setup.entry_type:
            confidence += 0.10
            if setup.entry_type == 'FVG':
                confidence += 0.05  # FVG slightly better than OB
        
        # Liquidity level strength
        if setup.swept_level.strength >= 2:
            confidence += 0.10
        
        # Risk-reward check
        if setup.risk_reward and setup.risk_reward >= 2:
            confidence += 0.10
        
        return min(confidence, 1.0)
    
    def get_active_setups(self) -> List[TurtleSoupSetup]:
        """Get currently active setups"""
        return [s for s in self.active_setups 
                if s.status in [SweepStatus.CONFIRMED, SweepStatus.ENTRY_READY, SweepStatus.ACTIVE]]
    
    def format_setup(self, setup: TurtleSoupSetup) -> str:
        """Format setup for display"""
        direction = "🟢 LONG" if setup.type == TurtleSoupType.BULLISH else "🔴 SHORT"
        
        lines = [
            f"═══ TURTLE SOUP {direction} ═══",
            f"Status: {setup.status.value.upper()}",
            f"Swept Level: {setup.swept_level}",
        ]
        
        if setup.mss_confirmed:
            lines.append(f"MSS Confirmed @ {setup.mss_level:.5f}")
        
        if setup.entry_type:
            lines.append(f"Entry Zone ({setup.entry_type}): {setup.entry_zone_low:.5f} - {setup.entry_zone_high:.5f}")
        
        if setup.entry_price:
            lines.extend([
                f"Entry: {setup.entry_price:.5f}",
                f"Stop: {setup.stop_loss:.5f}",
                f"Target: {setup.take_profit:.5f}",
                f"R:R = 1:{setup.risk_reward:.1f}" if setup.risk_reward else ""
            ])
        
        lines.append(f"Confidence: {setup.confidence*100:.0f}%")
        
        return "\n".join(filter(None, lines))


# Convenience function
def detect_turtle_soup(df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> List[TurtleSoupSetup]:
    """Quick detection of Turtle Soup patterns"""
    detector = TurtleSoupDetector()
    return detector.analyze(df, symbol, timeframe)
